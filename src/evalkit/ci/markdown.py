"""Render a :class:`RegressionReport` as a GitHub-flavoured Markdown PR comment.

The comment is intentionally compact and visual, emoji status markers, a
metrics table, and an explicit verdict line at the bottom. This is the
artifact people see in the PR conversation; making it skimmable matters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from evalkit.diff.differ import MetricDelta, RegressionReport


_HEADER = "<!-- evalkit:pr-comment -->\n## EvalKit report\n"


def render_pr_comment(report: RegressionReport) -> str:
    """Return the full Markdown body for a PR comment."""
    lines: list[str] = [_HEADER]

    if report.has_regressions:
        n = len(report.regressions)
        lines.append(
            f"### ❌ {n} metric{'s' if n != 1 else ''} regressed beyond "
            f"{report.threshold_pp:.1f}pp threshold\n",
        )
    elif not report.deltas:
        lines.append("### ⚪ No comparable metrics\n")
    else:
        lines.append("### ✅ No regressions\n")

    lines.append("| Metric | Baseline | Current | Δ | Status |")
    lines.append("|---|---:|---:|---:|:---:|")
    for d in report.deltas:
        emoji = _emoji_for(d)
        sign = "+" if d.delta_pp >= 0 else ""
        lines.append(
            f"| `{d.name}` | {d.baseline:.3f} | {d.current:.3f} | "
            f"{sign}{d.delta_pp:.1f}pp | {emoji} |",
        )

    if report.added:
        lines.append("\n**Added metrics:** " + ", ".join(f"`{m}`" for m in report.added))
    if report.removed:
        lines.append("**Removed metrics:** " + ", ".join(f"`{m}`" for m in report.removed))

    lines.append("\n<details><summary>Run metadata</summary>\n")
    lines.append(_meta_block("baseline", report.baseline_meta))
    lines.append(_meta_block("current", report.current_meta))
    lines.append("</details>\n")

    lines.append(
        "\n<sub>Posted by [EvalKit](https://github.com/AmirD10224/eval-kit) · "
        f"threshold: {report.threshold_pp:.1f}pp</sub>",
    )
    return "\n".join(lines)


def _emoji_for(d: MetricDelta) -> str:
    if d.is_regression:
        return "❌"
    if abs(d.delta_pp) < 0.5:
        return "▪️"
    return "✅" if (d.delta_pp > 0) == d.higher_is_better else "⚠️"


def _meta_block(label: str, meta: dict[str, object]) -> str:
    lines = [f"**{label}**"]
    for k in sorted(meta):
        lines.append(f"- `{k}`: `{meta[k]}`")
    return "\n".join(lines) + "\n"
