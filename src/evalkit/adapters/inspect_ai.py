"""Inspect AI adapter, convert an EvalKit suite into an Inspect AI ``Task``.

Inspect AI is the UK AI Safety Institute's eval framework. The bridge here is
intentionally thin: take a :class:`SuiteConfig`, return an Inspect ``Task``
whose dataset and scorers are derived from EvalKit's. Users who already have
Inspect plumbing can drop EvalKit suites in without rewriting harness code.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from evalkit.exceptions import AdapterError

if TYPE_CHECKING:  # pragma: no cover
    from evalkit.config import SuiteConfig


def to_inspect_task(suite: SuiteConfig, suite_dir: Path) -> Any:
    """Build an ``inspect_ai.Task`` from an EvalKit :class:`SuiteConfig`.

    Returns the Task object so the caller can hand it to ``inspect eval``.

    Raises:
        AdapterError: if Inspect AI isn't installed.
    """
    try:
        from inspect_ai import Task  # noqa: PLC0415
        from inspect_ai.dataset import Sample, json_dataset  # noqa: PLC0415
        from inspect_ai.scorer import Score, Target, scorer  # noqa: PLC0415
        from inspect_ai.solver import generate  # noqa: PLC0415
    except ImportError as exc:
        raise AdapterError(
            "inspect-ai not installed. Install with: pip install 'evalkit-oss[inspect]'",
        ) from exc

    dataset_path = (suite_dir / suite.dataset).resolve()

    def _record_to_sample(record: dict[str, Any]) -> Sample:
        return Sample(
            id=record["id"],
            input=str(record.get("input", "")),
            target=str(record.get("expected", "") or ""),
            metadata=dict(record.get("metadata") or {}),
        )

    @scorer(metrics=["accuracy"])  # type: ignore[untyped-decorator]
    def _passthrough_scorer() -> Any:
        async def _score(state: Any, target: Target) -> Score:
            output = state.output.completion if state.output else ""
            ok = bool(output) and (str(target.text) in output if target.text else True)
            return Score(value=1.0 if ok else 0.0, answer=output)

        return _score

    return Task(
        dataset=json_dataset(str(dataset_path), _record_to_sample),
        solver=generate(),
        scorer=_passthrough_scorer(),
        name=suite.name,
    )
