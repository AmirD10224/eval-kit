"""Bias audit tests using stub judges.

Pairwise audits (position, self-preference) require the judge's rubric to
expose ``A`` and ``B`` as criterion names, that's the structural form that
makes those audits meaningful. Point-wise stubs use a single criterion.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from evalkit.exceptions import BiasDetected, JudgeError
from evalkit.judges.base import JudgeOutput
from evalkit.judges.bias import (
    BiasReport,
    audit_biases,
    audit_length_bias,
    audit_position_bias,
    audit_self_preference,
    is_pairwise_rubric,
)
from evalkit.judges.rubric import Rubric

_PAIRWISE_RUBRIC_YAML = """\
name: pairwise
description: pairwise comparison rubric
criteria:
  - name: A
    description: rate slot A
    scale: 5
  - name: B
    description: rate slot B
    scale: 5
"""

_POINTWISE_RUBRIC_YAML = """\
name: pointwise
description: simple length scoring
criteria:
  - name: len
    description: rate length
    scale: 5
"""


class _ConstantPairwiseJudge:
    """Pairwise judge that returns the same per-slot scores every call."""

    def __init__(self, a: int, b: int) -> None:
        self.rubric = Rubric.from_text(_PAIRWISE_RUBRIC_YAML)
        self._a = a
        self._b = b

    def score(
        self,
        *,
        input_data: Mapping[str, Any],
        output_data: Mapping[str, Any],
        expected: Mapping[str, Any] | None = None,
    ) -> JudgeOutput:
        return JudgeOutput(
            score=0.5,
            criterion_scores={"A": self._a, "B": self._b},
            reasoning="stub",
            raw_response="",
        )


class _AlwaysPickAJudge:
    """Always picks slot A; pure position bias."""

    def __init__(self) -> None:
        self.rubric = Rubric.from_text(_PAIRWISE_RUBRIC_YAML)

    def score(
        self,
        *,
        input_data: Mapping[str, Any],
        output_data: Mapping[str, Any],
        expected: Mapping[str, Any] | None = None,
    ) -> JudgeOutput:
        return JudgeOutput(
            score=1.0,
            criterion_scores={"A": 5, "B": 1},
            reasoning="A always",
            raw_response="",
        )


class _LengthBiasedJudge:
    """Point-wise judge whose score grows with answer length."""

    def __init__(self) -> None:
        self.rubric = Rubric.from_text(_POINTWISE_RUBRIC_YAML)

    def score(
        self,
        *,
        input_data: Mapping[str, Any],
        output_data: Mapping[str, Any],
        expected: Mapping[str, Any] | None = None,
    ) -> JudgeOutput:
        text = str(output_data.get("answer", ""))
        s = min(1.0, len(text) / 200.0)
        return JudgeOutput(
            score=s,
            criterion_scores={"len": int(s * 5) + 1},
            reasoning="",
            raw_response="",
        )


# ---------- pairwise audits ----------------------------------------------


def test_position_bias_detected() -> None:
    judge = _AlwaysPickAJudge()
    bias = audit_position_bias(judge, n_pairs=8)
    assert bias > 0.5


def test_position_bias_no_bias_returns_zero() -> None:
    judge = _ConstantPairwiseJudge(a=3, b=3)
    assert audit_position_bias(judge, n_pairs=4) == 0.0


def test_position_bias_requires_pairwise_rubric() -> None:
    judge = _LengthBiasedJudge()
    with pytest.raises(JudgeError, match="pairwise"):
        audit_position_bias(judge, n_pairs=4)


def test_self_preference_requires_pairwise_rubric() -> None:
    judge = _LengthBiasedJudge()
    with pytest.raises(JudgeError, match="pairwise"):
        audit_self_preference(judge, [], [])


def test_self_preference_zero_when_inputs_missing() -> None:
    judge = _ConstantPairwiseJudge(a=3, b=3)
    assert audit_self_preference(judge, [], []) == 0.0


def test_is_pairwise_rubric_helper() -> None:
    assert is_pairwise_rubric(_AlwaysPickAJudge()) is True
    assert is_pairwise_rubric(_LengthBiasedJudge()) is False


# ---------- length audit (universal) -------------------------------------


def test_length_bias_detected() -> None:
    judge = _LengthBiasedJudge()
    short_long = [("hi", "hi" + "x" * 200)] * 4
    bias = audit_length_bias(judge, short_long)
    assert bias > 0.1


def test_length_bias_empty() -> None:
    assert audit_length_bias(_LengthBiasedJudge(), short_long_pairs=[]) == 0.0


def test_length_bias_default_filler_is_neutral() -> None:
    """Default filler must be content-neutral whitespace, not assertions."""
    judge = _LengthBiasedJudge()
    bias = audit_length_bias(judge, n_pairs=4)
    # Length-biased judge: long version scores higher → bias > 0.
    assert bias > 0.0


# ---------- driver --------------------------------------------------------


def test_audit_biases_pointwise_skips_position() -> None:
    judge = _LengthBiasedJudge()
    report = audit_biases(judge, threshold=0.5, n_pairs=4)
    assert report.length_bias is not None
    assert report.position_bias is None  # N/A for non-pairwise
    assert report.self_pref_bias is None
    assert "position" not in report.channels


def test_audit_biases_pairwise_runs_position() -> None:
    judge = _AlwaysPickAJudge()
    report = audit_biases(judge, threshold=0.05, n_pairs=4)
    assert report.position_bias is not None
    assert "position" in report.channels


def test_bias_report_raise_if_failing() -> None:
    judge = _AlwaysPickAJudge()
    report = audit_biases(judge, threshold=0.05, n_pairs=4)
    assert not report.passes()
    with pytest.raises(BiasDetected):
        report.raise_if_failing()


def test_bias_report_worst_picks_max_abs() -> None:
    r = BiasReport(length_bias=-0.4, position_bias=0.1, self_pref_bias=0.0, threshold=0.5)
    worst = r.worst
    assert worst is not None
    kind, mag = worst
    assert kind == "length"
    assert mag == pytest.approx(-0.4)


def test_bias_report_passes_when_all_channels_none() -> None:
    """Vacuously passes if no audit was run."""
    r = BiasReport(length_bias=None, position_bias=None, self_pref_bias=None, threshold=0.15)
    assert r.passes() is True
    assert r.worst is None
    r.raise_if_failing()  # must not raise
