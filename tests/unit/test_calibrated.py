"""Tests for the calibrated judge, calibration, scoring, parse errors."""

from __future__ import annotations

import json

import pytest

from evalkit.exceptions import CalibrationFailure, DatasetError, JudgeError
from evalkit.judges.calibrated import CalibratedJudge, _bin_aggregate, _coerce_human_score
from evalkit.llm.stub import StubClient


def _preds_from_golden(rows: list) -> dict[str, dict]:  # type: ignore[type-arg]
    """Build a {row_id: output_dict} mapping from a list of golden rows.

    For these stubbed tests the "candidate" output is the gold answer (the
    judge stub reads scores from the prompt); using a real predictions
    mapping silences the deprecation warning emitted when calibrate is
    called without one.
    """
    return {row.id: dict(row.expected or {}) for row in rows}


def test_judge_score_returns_aggregate(calibrated_judge: CalibratedJudge) -> None:
    out = calibrated_judge.score(
        input_data={"question": "q"},
        output_data={"answer": "a"},
        expected={"grounded": 5, "no_invention": 5},
    )
    assert 0.0 <= out.score <= 1.0
    assert set(out.criterion_scores.keys()) == {"grounded", "no_invention"}


def test_judge_handles_score_field_fallback(rubric_yaml: str) -> None:
    """When the LLM returns ``{"score": N}`` instead of per-criterion, broadcast N."""
    client = StubClient(default_response='{"score": 4}')
    judge = CalibratedJudge.from_rubric_text(rubric_yaml, client=client)
    out = judge.score(input_data={}, output_data={})
    assert out.criterion_scores == {"grounded": 4, "no_invention": 4}


def test_judge_unparseable_response_raises(rubric_yaml: str) -> None:
    client = StubClient(default_response="not json at all")
    judge = CalibratedJudge.from_rubric_text(rubric_yaml, client=client)
    with pytest.raises(JudgeError, match="JSON"):
        judge.score(input_data={}, output_data={})


def test_judge_non_object_response_raises(rubric_yaml: str) -> None:
    client = StubClient(default_response="[1, 2, 3]")
    judge = CalibratedJudge.from_rubric_text(rubric_yaml, client=client)
    with pytest.raises(JudgeError, match="JSON object"):
        judge.score(input_data={}, output_data={})


def test_judge_missing_criterion_raises(rubric_yaml: str) -> None:
    client = StubClient(default_response=json.dumps({"grounded": 4}))  # no_invention missing
    judge = CalibratedJudge.from_rubric_text(rubric_yaml, client=client)
    with pytest.raises(JudgeError, match="no_invention"):
        judge.score(input_data={}, output_data={})


def test_judge_handles_fenced_response(rubric_yaml: str) -> None:
    client = StubClient(default_response='```json\n{"grounded": 5, "no_invention": 5}\n```')
    judge = CalibratedJudge.from_rubric_text(rubric_yaml, client=client)
    out = judge.score(input_data={}, output_data={})
    assert out.score == pytest.approx(1.0)


# ---------- calibration ---------------------------------------------------


def test_calibration_passes_when_judge_mirrors_humans(
    calibrated_judge: CalibratedJudge,
    golden_path,  # type: ignore[no-untyped-def]
    golden_rows,  # type: ignore[no-untyped-def]
) -> None:
    report = calibrated_judge.calibrate(
        golden_path,
        predictions=_preds_from_golden(golden_rows),
        run_bias_audit=False,
    )
    assert report.passes
    assert report.cohen_kappa > 0.5
    assert report.failure_reason is None
    # New paradox diagnostics surface alongside κ.
    assert 0.0 <= report.prevalence_index <= 1.0
    assert 0.0 <= report.bias_index <= 1.0


def test_calibration_fails_when_judge_diverges(
    rubric_yaml: str,
    golden_path,  # type: ignore[no-untyped-def]
    golden_rows,  # type: ignore[no-untyped-def]
) -> None:
    """Stub always returns 1; humans label 1..5, expect kappa near zero."""
    client = StubClient(default_response='{"grounded": 1, "no_invention": 1}')
    judge = CalibratedJudge.from_rubric_text(rubric_yaml, client=client)
    report = judge.calibrate(
        golden_path,
        predictions=_preds_from_golden(golden_rows),
        run_bias_audit=False,
    )
    assert not report.passes
    assert report.failure_reason is not None


def test_calibration_raises_when_asked(
    rubric_yaml: str,
    golden_path,  # type: ignore[no-untyped-def]
    golden_rows,  # type: ignore[no-untyped-def]
) -> None:
    client = StubClient(default_response='{"grounded": 1, "no_invention": 1}')
    judge = CalibratedJudge.from_rubric_text(rubric_yaml, client=client)
    with pytest.raises(CalibrationFailure):
        judge.calibrate(
            golden_path,
            predictions=_preds_from_golden(golden_rows),
            run_bias_audit=False,
            raise_on_fail=True,
        )


def test_calibration_too_few_rows(
    calibrated_judge: CalibratedJudge,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    p = tmp_path / "tiny.jsonl"
    p.write_text(
        '{"id": "a", "input": {}, "expected": {}, "labels": [{"score": 1}, {"score": 1}]}\n',
    )
    report = calibrated_judge.calibrate(
        p,
        predictions={"a": {}},
        run_bias_audit=False,
    )
    assert not report.passes
    assert report.failure_reason is not None
    assert "≥" in report.failure_reason or "min" in report.failure_reason.lower()


def test_calibration_no_human_labels(
    rubric_yaml: str,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    p = tmp_path / "unlabelled.jsonl"
    with p.open("w") as f:
        for i in range(15):
            f.write(json.dumps({"id": f"r-{i}", "input": {}, "labels": []}) + "\n")
    client = StubClient(default_response='{"grounded": 3, "no_invention": 3}')
    judge = CalibratedJudge.from_rubric_text(rubric_yaml, client=client)
    report = judge.calibrate(
        p,
        predictions={f"r-{i}": {} for i in range(15)},
        run_bias_audit=False,
    )
    assert not report.passes
    assert report.failure_reason is not None
    assert "human labels" in report.failure_reason or "min" in report.failure_reason.lower()


def test_calibration_legacy_predictions_none_warns(
    calibrated_judge: CalibratedJudge,
    golden_path,  # type: ignore[no-untyped-def]
) -> None:
    """``predictions=None`` is the legacy path; must emit a DeprecationWarning."""
    with pytest.warns(DeprecationWarning, match="predictions"):
        calibrated_judge.calibrate(golden_path, run_bias_audit=False)


def test_calibration_predictions_path_loads_jsonl(
    calibrated_judge: CalibratedJudge,
    golden_path,  # type: ignore[no-untyped-def]
    golden_rows,  # type: ignore[no-untyped-def]
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Predictions accept a JSONL path with ``{"id": ..., "output": ...}`` rows."""
    pred_path = tmp_path / "preds.jsonl"
    with pred_path.open("w") as f:
        for row in golden_rows:
            f.write(json.dumps({"id": row.id, "output": dict(row.expected or {})}))
            f.write("\n")
    report = calibrated_judge.calibrate(
        golden_path,
        predictions=pred_path,
        run_bias_audit=False,
    )
    assert report.passes


def test_calibration_predictions_path_missing_id_raises(
    calibrated_judge: CalibratedJudge,
    golden_path,  # type: ignore[no-untyped-def]
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    """Mis-aligned predictions JSONL raises a clear DatasetError."""
    pred_path = tmp_path / "bad.jsonl"
    pred_path.write_text(json.dumps({"id": "row-000", "output": {}}) + "\n")
    with pytest.raises(DatasetError, match="missing"):
        calibrated_judge.calibrate(
            golden_path,
            predictions=pred_path,
            run_bias_audit=False,
        )


def test_report_to_dict_roundtrip(
    calibrated_judge: CalibratedJudge,
    golden_path,  # type: ignore[no-untyped-def]
    golden_rows,  # type: ignore[no-untyped-def]
) -> None:
    report = calibrated_judge.calibrate(
        golden_path,
        predictions=_preds_from_golden(golden_rows),
        run_bias_audit=False,
    )
    d = report.to_dict()
    assert d["passes"] is True
    assert "cohen_kappa" in d
    assert "prevalence_index" in d
    assert "bias_index" in d
    assert "gwet_ac1" in d
    assert "scale" in d


# ---------- helpers --------------------------------------------------------


def test_bin_aggregate_clamps_and_centers() -> None:
    """Boundary semantics: midpoint maps to the middle bin, not bin 1.

    Old impl had a banker's-rounding asymmetry where 0.5 mapped to bin 1.
    Fixed boundaries: 0.0..0.125 → 1, 0.125..0.375 → 2, 0.375..0.625 → 3, ...
    """
    assert _bin_aggregate(-0.1) == 1
    assert _bin_aggregate(0.0) == 1
    assert _bin_aggregate(1.0) == 5
    assert _bin_aggregate(1.5) == 5
    assert _bin_aggregate(0.5) == 3
    # Midpoint between bins on a 1..5 scale at 0.125 lands in bin 2 (no longer bin 1).
    assert _bin_aggregate(0.125) == 2


def test_bin_aggregate_respects_scale() -> None:
    """Scale is now configurable from the rubric, not hardcoded to 5."""
    assert _bin_aggregate(0.5, scale=10) == 6
    assert _bin_aggregate(1.0, scale=10) == 10
    assert _bin_aggregate(0.0, scale=10) == 1


def test_coerce_human_score_uses_median_for_ordinal() -> None:
    """Median collapses ordinal labels (mode tie-break biases toward lower)."""
    out = _coerce_human_score(
        [{"rater": "a", "score": 4}, {"rater": "b", "score": 4}, {"rater": "c", "score": 5}],
        scale=5,
    )
    assert out == {"median": 4, "all": [4, 4, 5]}


def test_coerce_human_score_clamps_to_scale() -> None:
    """A median above the rubric scale is clamped, defensive for malformed labels."""
    out = _coerce_human_score(
        [{"rater": "a", "score": 7}, {"rater": "b", "score": 8}],
        scale=5,
    )
    assert out is not None
    assert out["median"] == 5  # clamped


def test_coerce_human_score_returns_none_when_empty() -> None:
    assert _coerce_human_score([]) is None
    assert _coerce_human_score([{"rater": "x", "score": "not a number"}]) is None
