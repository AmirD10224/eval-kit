"""Render a Markdown PR comment to a PNG using Playwright.

Strategy: render the Markdown to HTML with a github-ish stylesheet, drop it
into a chromium page at a fixed viewport, screenshot. The output looks
close enough to a real GitHub PR comment to pass at a glance, which is
exactly what the marketing screenshot needs to do.

This module is excluded from coverage (Playwright + a real browser don't
belong in unit tests); we ship an integration smoke that's run manually.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from evalkit.exceptions import AdapterError

_GITHUB_CSS = """
:root {
  --bg: #ffffff;
  --fg: #1f2328;
  --muted: #59636e;
  --border: #d1d9e0;
  --code-bg: #f6f8fa;
  --green: #1a7f37;
  --red: #d1242f;
  --yellow: #9a6700;
  --blue: #0969da;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 24px;
  background: #f6f8fa;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial,
               sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
  color: var(--fg); font-size: 14px; line-height: 1.5;
}
.comment {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 12px; max-width: 940px; margin: 0 auto;
}
.comment-header {
  background: #f6f8fa; border-bottom: 1px solid var(--border);
  padding: 8px 16px; border-radius: 12px 12px 0 0;
  font-size: 13px; color: var(--muted);
}
.comment-header strong { color: var(--fg); }
.comment-body { padding: 16px; }
.comment-body h2 { font-size: 18px; margin: 0 0 8px; }
.comment-body h3 { font-size: 16px; margin: 16px 0 8px; }
.comment-body table {
  border-collapse: collapse; width: 100%;
  margin: 12px 0; font-size: 13px;
}
.comment-body th, .comment-body td {
  border: 1px solid var(--border); padding: 6px 13px; text-align: left;
}
.comment-body th { background: var(--code-bg); font-weight: 600; }
.comment-body td.numeric, .comment-body th.numeric { text-align: right; }
.comment-body td.center, .comment-body th.center { text-align: center; }
.comment-body code {
  background: var(--code-bg); padding: 1px 6px; border-radius: 6px;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
  font-size: 85%;
}
.comment-body details {
  border: 1px solid var(--border); border-radius: 6px;
  padding: 8px 12px; margin: 12px 0; background: #fafbfc;
}
.comment-body summary { cursor: pointer; color: var(--muted); }
.comment-body sub { color: var(--muted); }
.tag-fail {
  display: inline-block; padding: 2px 8px;
  border-radius: 999px; background: #ffebe9; color: var(--red);
  font-weight: 600; font-size: 12px;
}
.check-row {
  display: flex; align-items: center; gap: 8px;
  border-top: 1px solid var(--border); padding: 12px 16px;
  font-size: 13px;
}
.check-row .x { color: var(--red); font-weight: 700; }
"""


def render_pr_comment_to_png(
    markdown_body: str,
    output_path: str | Path,
    *,
    pr_title: str = "Tweak retrieval prompt for better recall",
    author: str = "AmirD10224",
    repo: str = "AmirD10224/sample-rag-app",
    pr_number: int = 42,
    width: int = 1024,
    show_check_row: bool = True,
) -> Path:
    """Render the markdown to PNG.

    Requires the ``[render]`` extra (Playwright + Jinja2). On the first call
    you must have ``playwright install chromium`` already run.

    Args:
        markdown_body: the body produced by
            :func:`evalkit.ci.markdown.render_pr_comment`.
        output_path: where to save the PNG.
        pr_title, author, repo, pr_number: cosmetic fields shown in the header.
        width: viewport width.
        show_check_row: render a fake "EvalKit / metrics. Failing after 1m 32s"
            check row at the bottom (the part that makes the screenshot pop).
    """
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise AdapterError(
            "rendering requires the [render] extra: pip install 'evalkit-oss[render]' "
            "and run `playwright install chromium` once.",
        ) from exc

    html_body = _markdown_to_html(markdown_body)
    page_html = _build_page(
        html_body=html_body,
        pr_title=pr_title,
        author=author,
        repo=repo,
        pr_number=pr_number,
        show_check_row=show_check_row,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 800})
        page.set_content(page_html, wait_until="domcontentloaded")
        # Take a clip-style screenshot of just the comment + check row.
        element = page.locator(".outer")
        element.screenshot(path=str(output_path))
        browser.close()
    return output_path


# ---------------------------------------------------------------------------
# Mini Markdown → HTML. only the subset our PR comment uses.
# Robust enough for our rendered comments; not a general-purpose engine.


def _markdown_to_html(md: str) -> str:
    md = re.sub(r"<!--.*?-->", "", md, flags=re.DOTALL)  # strip HTML comments
    out_lines: list[str] = []
    in_table = False
    in_details = False
    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            if in_table:
                out_lines.append("</tbody></table>")
                in_table = False
            out_lines.append("")
            continue
        if line.startswith("## "):
            out_lines.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("### "):
            out_lines.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", c) for c in cells):
                continue  # alignment row
            if not in_table:
                out_lines.append("<table><thead>")
                out_lines.append(
                    "<tr>" + "".join(f"<th>{_inline(c)}</th>" for c in cells) + "</tr>"
                )
                out_lines.append("</thead><tbody>")
                in_table = True
            else:
                out_lines.append(
                    "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>",
                )
        elif line.startswith("<details>"):
            out_lines.append("<details>")
            in_details = True
        elif line.startswith("</details>"):
            out_lines.append("</details>")
            in_details = False
        elif line.startswith("<summary>") and in_details:
            out_lines.append(line)
        elif line.startswith("**") and line.endswith("**"):
            out_lines.append(f"<p><strong>{_inline(line[2:-2])}</strong></p>")
        else:
            out_lines.append(f"<p>{_inline(line)}</p>")
    if in_table:
        out_lines.append("</tbody></table>")
    return "\n".join(out_lines)


def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"&lt;sub&gt;(.*?)&lt;/sub&gt;", r"<sub>\1</sub>", text)
    text = re.sub(r"&lt;summary&gt;(.*?)&lt;/summary&gt;", r"<summary>\1</summary>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2">\1</a>',
        text,
    )


def _build_page(
    *,
    html_body: str,
    pr_title: str,
    author: str,  # noqa: ARG001, reserved for future header rendering
    repo: str,
    pr_number: int,
    show_check_row: bool,
) -> str:
    check_row = (
        '<div class="check-row"><span class="x">✗</span>'
        "<strong>EvalKit / metrics</strong>"
        '<span class="comment-header">Failing after 1m 32s. '
        "regressions exceed configured threshold</span></div>"
        if show_check_row
        else ""
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(pr_title)}</title>
<style>{_GITHUB_CSS}</style></head>
<body>
<div class="outer" style="max-width:980px;margin:0 auto;">
  <div class="comment">
    <div class="comment-header">
      <strong>evalkit-bot</strong> commented on
      <a href="#">{html.escape(repo)} #{pr_number}</a>:
      <em>{html.escape(pr_title)}</em>
    </div>
    <div class="comment-body">
      {html_body}
    </div>
  </div>
  {check_row}
</div>
</body></html>"""
