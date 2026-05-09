"""Entrypoint for the EvalKit GitHub Action.

Executes the suite on the current checkout, resolves a baseline (either an
existing JSON report path or a git ref), diffs the two, posts a Markdown
comment to the PR, and exits non-zero when regressions exceed the threshold.

The action delegates to the installed `evalkit` Python package, this script
is just glue around environment variables that GitHub injects.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from evalkit.ci.github import GitHubError, post_pr_comment
from evalkit.ci.markdown import render_pr_comment
from evalkit.diff.differ import diff_reports
from evalkit.exceptions import EvalKitError
from evalkit.llm.client import AnthropicClient
from evalkit.runner.report import SuiteReport
from evalkit.runner.runner import Suite


def _env(name: str, *, required: bool = True, default: str | None = None) -> str:
    value = os.environ.get(name, default or "")
    if required and not value:
        print(f"::error::missing required env var {name}", file=sys.stderr)
        sys.exit(2)
    return value


def _set_output(name: str, value: str) -> None:
    """Append to GITHUB_OUTPUT so subsequent steps can consume the value."""
    out_path = os.environ.get("GITHUB_OUTPUT")
    if not out_path:
        print(f"{name}={value}")
        return
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(f"{name}={value}\n")


def _resolve_baseline(
    baseline: str,
    suite_path: Path,
) -> SuiteReport:
    """``baseline`` is either a JSON report path or a git ref.

    For a git ref, check out that ref in a sibling worktree and run the
    *same* suite YAML (resolved by its repo-relative path) inside that
    worktree. Earlier we hard-coded the worktree suite path as
    ``<work>/<base_dir.name>/suite.yaml`` which silently dropped any
    intermediate directories and failed for any user whose suite isn't
    literally named ``suite.yaml``.

    Args:
        baseline: git ref ("main", "abc123", "v0.2.0") or path to a JSON report.
        suite_path: the suite YAML path on the *current* checkout, used to
            derive the repo-relative path we re-load inside the worktree.

    Raises if the suite path lives outside the git repo, or if a baseline
    git ref doesn't exist.
    """
    p = Path(baseline)
    if p.is_file() and p.suffix == ".json":
        return SuiteReport.load(p)

    repo_root = _git_toplevel(suite_path.parent)
    suite_rel = suite_path.resolve().relative_to(repo_root)
    work = Path(".evalkit-baseline-worktree").resolve()
    if work.exists():
        subprocess.run(["git", "worktree", "remove", "--force", str(work)], check=False)
    # ``--`` separator: defends against a future caller wiring user-controlled
    # data into ``baseline`` (e.g., a github.event field that could begin
    # with "--"). Cheap belt-and-braces.
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(work), "--", baseline],
        check=True,
    )
    try:
        worktree_suite = Suite.from_yaml(work / suite_rel)
        report = worktree_suite.run(client=AnthropicClient()).report
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(work)], check=False)
    return report


def _git_toplevel(start: Path) -> Path:
    """Return the git repository root for ``start``."""
    out = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return Path(out.stdout.strip()).resolve()


def main() -> int:
    suite_path = Path(_env("EVALKIT_SUITE"))
    baseline = _env("EVALKIT_BASELINE")
    output_path = Path(_env("EVALKIT_OUTPUT"))
    threshold = float(_env("EVALKIT_THRESHOLD"))
    comment = _env("EVALKIT_COMMENT", required=False, default="true").lower() == "true"
    predictions = os.environ.get("EVALKIT_PREDICTIONS") or None

    try:
        client = AnthropicClient()
    except EvalKitError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    suite = Suite.from_yaml(suite_path)
    current = suite.run(client=client, predictions=predictions).report
    current.save(output_path)
    _set_output("report_path", str(output_path))

    try:
        baseline_report = _resolve_baseline(baseline, suite_path)
    except (subprocess.SubprocessError, EvalKitError, OSError, ValueError) as exc:
        print(
            f"::warning::could not resolve baseline {baseline!r} ({exc}); "
            "skipping diff and posting raw report only.",
            file=sys.stderr,
        )
        _set_output("has_regressions", "false")
        return 0

    diff = diff_reports(baseline_report, current, threshold_pp=threshold)
    body = render_pr_comment(diff)

    if comment:
        try:
            post_pr_comment(body=body)
        except GitHubError as exc:
            print(f"::warning::could not post PR comment: {exc}", file=sys.stderr)

    print(body)
    print(json.dumps(diff.to_dict(), indent=2))
    _set_output("has_regressions", "true" if diff.has_regressions else "false")
    return 1 if diff.has_regressions else 0


if __name__ == "__main__":
    raise SystemExit(main())
