"""Generate docs/screenshots/auto-reject.png from baseline.json + current.json.

Runs the EvalKit diff, renders the resulting PR-comment Markdown to a PNG via
Playwright, and writes it to ``docs/screenshots/auto-reject.png`` so it's
ready to ship in the README.

Requires the ``[render]`` extra:

    pip install "evalkit-oss[render]"
    playwright install chromium
"""

from __future__ import annotations

import sys
from pathlib import Path

from evalkit.ci.markdown import render_pr_comment
from evalkit.diff.differ import diff_reports
from evalkit.runner.report import SuiteReport

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
SCREENSHOT_PATH = REPO_ROOT / "docs" / "screenshots" / "auto-reject.png"
EXPECTED_MD = HERE / "expected_pr_comment.md"


def main() -> int:
    baseline = SuiteReport.load(HERE / "baseline.json")
    current = SuiteReport.load(HERE / "current.json")
    diff = diff_reports(baseline, current, threshold_pp=5.0)
    body = render_pr_comment(diff)
    EXPECTED_MD.write_text(body, encoding="utf-8")
    print(f"wrote markdown → {EXPECTED_MD.relative_to(REPO_ROOT)}")

    try:
        from evalkit.render.screenshot import render_pr_comment_to_png
    except ImportError as exc:
        print(f"warning: render extra not installed ({exc})", file=sys.stderr)
        print("install with: pip install 'evalkit-oss[render]' && playwright install chromium")
        return 0

    try:
        out = render_pr_comment_to_png(
            body,
            SCREENSHOT_PATH,
            pr_title="Tweak retrieval prompt for better recall",
            author="AmirD10224",
            repo="AmirD10224/sample-rag-app",
            pr_number=42,
        )
    except Exception as exc:  # noqa: BLE001, surface anything from playwright
        print(f"warning: screenshot rendering failed ({exc})", file=sys.stderr)
        print("did you run `playwright install chromium`?")
        return 0
    print(f"wrote screenshot → {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
