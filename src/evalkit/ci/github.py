"""GitHub REST API glue for posting (or upserting) a PR comment.

We use plain ``httpx`` rather than PyGithub, one HTTP endpoint, two if you
count comment listing for upsert, isn't worth a 300KB dep.

The action calls :func:`post_pr_comment` with the rendered Markdown body
and a marker. If a previous EvalKit comment exists (identified by the
HTML-comment marker in :data:`evalkit.ci.markdown._HEADER`), we update it
in place instead of spamming the PR with one comment per CI run.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

_API = "https://api.github.com"
_MARKER = "<!-- evalkit:pr-comment -->"


@dataclass(frozen=True, slots=True)
class PRRef:
    """Identifier for a pull request comment endpoint."""

    repo: str  # "owner/name"
    number: int


class GitHubError(Exception):
    """Raised on any non-2xx GitHub API response."""


def post_pr_comment(
    *,
    body: str,
    pr: PRRef | None = None,
    token: str | None = None,
    upsert: bool = True,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Post (or upsert) a comment on a PR.

    Args:
        body: Markdown body. Should start with the EvalKit marker for upsert.
        pr: target PR. If ``None`` we read ``GITHUB_REPOSITORY`` and
            ``PR_NUMBER`` from the environment.
        token: GitHub token. Defaults to ``GITHUB_TOKEN``.
        upsert: if True (the default), replace any existing EvalKit comment
            instead of appending a new one.
        client: optional pre-configured ``httpx.Client`` (used in tests).
    """
    pr = pr or _pr_from_env()
    token = token or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise GitHubError("GITHUB_TOKEN not set")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    owns_client = client is None
    c = client or httpx.Client(timeout=httpx.Timeout(30.0), headers=headers)
    try:
        if upsert:
            existing = _find_existing(c, pr, headers)
            if existing is not None:
                resp = c.patch(
                    f"{_API}/repos/{pr.repo}/issues/comments/{existing}",
                    headers=headers,
                    json={"body": body},
                )
                _raise_for_status(resp)
                return resp.json()  # type: ignore[no-any-return]
        resp = c.post(
            f"{_API}/repos/{pr.repo}/issues/{pr.number}/comments",
            headers=headers,
            json={"body": body},
        )
        _raise_for_status(resp)
        return resp.json()  # type: ignore[no-any-return]
    finally:
        if owns_client:
            c.close()


# ---- helpers --------------------------------------------------------------


def _find_existing(
    c: httpx.Client,
    pr: PRRef,
    headers: dict[str, str],
) -> int | None:
    page = 1
    while True:
        resp = c.get(
            f"{_API}/repos/{pr.repo}/issues/{pr.number}/comments",
            headers=headers,
            params={"per_page": 100, "page": page},
        )
        _raise_for_status(resp)
        items = resp.json()
        if not items:
            return None
        for item in items:
            body = item.get("body") or ""
            if _MARKER in body:
                return int(item["id"])
        if len(items) < 100:
            return None
        page += 1


def _pr_from_env() -> PRRef:
    repo = os.environ.get("GITHUB_REPOSITORY")
    number = os.environ.get("PR_NUMBER") or _pr_from_event_path()
    if not repo or not number:
        raise GitHubError(
            "GITHUB_REPOSITORY and PR_NUMBER must be set (or run inside a pull_request event)",
        )
    return PRRef(repo=repo, number=int(number))


def _pr_from_event_path() -> str | None:
    import json  # noqa: PLC0415

    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            event = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    pr = event.get("pull_request") or event.get("issue")
    if isinstance(pr, dict) and "number" in pr:
        return str(pr["number"])
    return None


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        raise GitHubError(f"GitHub API {resp.status_code}: {resp.text[:300]}")
