"""Ragas adapter, wrap selected Ragas metrics behind our scorer interface.

We don't reimplement faithfulness/context-precision/etc.; we delegate to
Ragas. The adapter only handles the sample shape conversion and gracefully
fails when the optional ``[ragas]`` extra isn't installed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from evalkit.exceptions import AdapterError

_SUPPORTED = {
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "context_relevancy",
    "answer_correctness",
}


class RagasScorer:
    """Adapter that turns ``(input, output, expected)`` into a Ragas single-sample score.

    Args:
        metric: Ragas metric name. Must be in :data:`_SUPPORTED`.

    Raises:
        AdapterError: if Ragas isn't installed or the metric is unknown.
    """

    def __init__(self, metric: str) -> None:
        if metric not in _SUPPORTED:
            raise AdapterError(
                f"unsupported ragas metric {metric!r}. Supported: {sorted(_SUPPORTED)}",
            )
        self._metric_name = metric
        self._metric = self._load_metric(metric)

    def score(
        self,
        input_data: Mapping[str, Any],
        output_data: Mapping[str, Any],
        expected: Mapping[str, Any] | None,
    ) -> float:
        sample = self._to_sample(input_data, output_data, expected)
        try:
            score = self._metric.single_turn_score(sample)
        except Exception as exc:
            raise AdapterError(f"ragas metric {self._metric_name!r} failed: {exc}") from exc
        try:
            return float(score)
        except (TypeError, ValueError) as exc:
            raise AdapterError(
                f"ragas metric {self._metric_name!r} returned non-numeric: {score!r}",
            ) from exc

    # ------------------------------------------------------------------

    @staticmethod
    def _load_metric(name: str) -> Any:
        try:
            import ragas  # noqa: F401, PLC0415
            from ragas.metrics import (  # noqa: PLC0415
                AnswerCorrectness,
                AnswerRelevancy,
                ContextPrecision,
                ContextRecall,
                ContextRelevancy,
                Faithfulness,
            )
        except ImportError as exc:
            raise AdapterError(
                "ragas not installed. Install with: pip install 'evalkit-oss[ragas]'",
            ) from exc
        ctor = {
            "faithfulness": Faithfulness,
            "answer_relevancy": AnswerRelevancy,
            "context_precision": ContextPrecision,
            "context_recall": ContextRecall,
            "context_relevancy": ContextRelevancy,
            "answer_correctness": AnswerCorrectness,
        }[name]
        return ctor()

    @staticmethod
    def _to_sample(
        input_data: Mapping[str, Any],
        output_data: Mapping[str, Any],
        expected: Mapping[str, Any] | None,
    ) -> Any:
        try:
            from ragas.dataset_schema import SingleTurnSample  # noqa: PLC0415
        except ImportError as exc:
            raise AdapterError(
                "ragas not installed. Install with: pip install 'evalkit-oss[ragas]'",
            ) from exc
        question = input_data.get("question") or input_data.get("input") or ""
        answer = output_data.get("answer") or output_data.get("output") or ""
        contexts = input_data.get("contexts") or input_data.get("context") or []
        if isinstance(contexts, str):
            contexts = [contexts]
        ground_truth = (expected or {}).get("answer") if expected else None
        return SingleTurnSample(
            user_input=str(question),
            response=str(answer),
            retrieved_contexts=[str(c) for c in contexts],
            reference=str(ground_truth) if ground_truth else None,
        )
