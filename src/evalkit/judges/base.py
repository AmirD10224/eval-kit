"""Judge protocol, the minimal interface every judge implements."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class JudgeOutput:
    """A single judge verdict.

    ``score`` is the weighted-aggregated score in [0, 1]; ``criterion_scores``
    keeps the raw per-criterion ints (1..N per the rubric scale) so callers
    can audit what drove the score.
    """

    score: float
    criterion_scores: Mapping[str, int]
    reasoning: str
    raw_response: str

    def is_pass(self, threshold: float = 0.7) -> bool:
        return self.score >= threshold


@runtime_checkable
class Judge(Protocol):
    """Anything that turns ``(input, output[, expected])`` into a :class:`JudgeOutput`."""

    def score(
        self,
        *,
        input_data: Mapping[str, Any],
        output_data: Mapping[str, Any],
        expected: Mapping[str, Any] | None = None,
    ) -> JudgeOutput: ...
