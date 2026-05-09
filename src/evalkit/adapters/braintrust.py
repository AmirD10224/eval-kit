"""Braintrust adapter, alternative report destination.

Drops in instead of (or alongside) the local JSON report. Same usage pattern
as the Langfuse adapter, optional dep, zero overhead when not used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from evalkit.exceptions import AdapterError

if TYPE_CHECKING:  # pragma: no cover
    from evalkit.runner.report import SuiteReport


def push_report(
    report: SuiteReport,
    *,
    project: str,
    experiment: str | None = None,
    api_key: str | None = None,
) -> str:
    """Push a :class:`SuiteReport` to Braintrust as an experiment.

    Returns the experiment URL.

    Raises:
        AdapterError: if ``braintrust`` is not installed.
    """
    try:
        import braintrust  # noqa: PLC0415
    except ImportError as exc:
        raise AdapterError(
            "braintrust not installed. Install with: pip install 'evalkit-oss[braintrust]'",
        ) from exc

    bt: Any = braintrust
    exp = bt.init(
        project=project,
        experiment=experiment or report.suite_name,
        api_key=api_key,
    )
    for metric in report.metrics:
        for sample in metric.samples:
            exp.log(
                input=sample.detail.get("input", {}),
                output=sample.detail.get("output", {}),
                expected=sample.detail.get("expected", {}),
                scores={metric.name: sample.score},
                metadata={"row_id": sample.row_id, **dict(sample.detail)},
            )
    summary = exp.summarize()
    return str(getattr(summary, "experiment_url", "") or "")
