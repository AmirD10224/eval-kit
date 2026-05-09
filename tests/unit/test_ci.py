"""Tests for ci/markdown.py and ci/github.py (using respx-style monkeypatching)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from evalkit.ci.github import GitHubError, PRRef, post_pr_comment
from evalkit.ci.markdown import render_pr_comment
from evalkit.diff.differ import diff_reports
from evalkit.runner.report import MetricResult, SuiteReport


def _report(name: str, **metrics: float) -> SuiteReport:
    return SuiteReport(
        suite_name=name,
        metrics=[MetricResult(name=k, kind="judge", mean=v, n=5) for k, v in metrics.items()],
        n_samples=5,
        judge_model="stub",
        timestamp="2026-05-06T00:00:00+00:00",
        duration_seconds=0.1,
        seed=0,
    )


def test_pr_comment_renders_regression_header() -> None:
    base = _report("a", faith=0.85)
    cur = _report("a", faith=0.70)
    md = render_pr_comment(diff_reports(base, cur, threshold_pp=5))
    assert "regressed" in md
    assert "❌" in md
    assert "faith" in md
    assert "<!-- evalkit:pr-comment -->" in md


def test_pr_comment_renders_clean_header() -> None:
    base = _report("a", faith=0.85)
    cur = _report("a", faith=0.86)
    md = render_pr_comment(diff_reports(base, cur, threshold_pp=5))
    assert "No regressions" in md


def test_pr_comment_renders_empty_when_no_overlap() -> None:
    base = _report("a", x=0.5)
    cur = _report("a", y=0.5)
    md = render_pr_comment(diff_reports(base, cur, threshold_pp=5))
    assert "No comparable metrics" in md
    assert "Added metrics" in md
    assert "Removed metrics" in md


# ---------- GitHub API stub -----------------------------------------------


class _MockTransport(httpx.MockTransport):
    pass


def test_post_pr_comment_creates_when_no_existing() -> None:
    posted: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=[])
        if request.method == "POST":
            posted["body"] = json.loads(request.content)
            return httpx.Response(201, json={"id": 1})
        return httpx.Response(404)

    with httpx.Client(transport=_MockTransport(handler)) as c:
        post_pr_comment(
            body="<!-- evalkit:pr-comment -->\nhello",
            pr=PRRef(repo="o/r", number=1),
            token="t",
            client=c,
        )
    assert posted["body"]["body"].startswith("<!-- evalkit:pr-comment -->")


def test_post_pr_comment_upserts_existing() -> None:
    patched: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json=[{"id": 99, "body": "<!-- evalkit:pr-comment -->\nold"}],
            )
        if request.method == "PATCH":
            patched["url"] = str(request.url)
            return httpx.Response(200, json={"id": 99})
        return httpx.Response(404)

    with httpx.Client(transport=_MockTransport(handler)) as c:
        post_pr_comment(
            body="<!-- evalkit:pr-comment -->\nnew",
            pr=PRRef(repo="o/r", number=1),
            token="t",
            client=c,
        )
    assert "/comments/99" in patched["url"]


def test_post_pr_comment_skip_upsert_when_disabled() -> None:
    seen_patch = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_patch
        if request.method == "PATCH":
            seen_patch = True
        if request.method == "POST":
            return httpx.Response(201, json={"id": 1})
        return httpx.Response(200, json=[])

    with httpx.Client(transport=_MockTransport(handler)) as c:
        post_pr_comment(
            body="x",
            pr=PRRef(repo="o/r", number=1),
            token="t",
            upsert=False,
            client=c,
        )
    assert not seen_patch


def test_post_pr_comment_no_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(GitHubError, match="GITHUB_TOKEN"):
        post_pr_comment(body="x", pr=PRRef(repo="o/r", number=1))


def test_post_pr_comment_api_error_propagates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    with httpx.Client(transport=_MockTransport(handler)) as c:
        with pytest.raises(GitHubError, match="403"):
            post_pr_comment(
                body="x",
                pr=PRRef(repo="o/r", number=1),
                token="t",
                upsert=False,
                client=c,
            )


def test_pr_from_env_when_no_args(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("PR_NUMBER", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    with pytest.raises(GitHubError, match="GITHUB_REPOSITORY"):
        post_pr_comment(body="x", token="t")


def test_pr_from_event_path(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 7}}))
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.delenv("PR_NUMBER", raising=False)
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_TOKEN", "t")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"id": 1})

    with httpx.Client(transport=_MockTransport(handler)) as c:
        post_pr_comment(body="x", upsert=False, client=c)
