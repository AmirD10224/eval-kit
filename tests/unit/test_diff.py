"""Regression-detection tests."""

from __future__ import annotations

from evalkit.diff.differ import diff_reports
from evalkit.runner.report import MetricResult, SuiteReport


def _report(name: str, **metrics: tuple[float, bool]) -> SuiteReport:
    return SuiteReport(
        suite_name=name,
        metrics=[
            MetricResult(name=k, kind="judge", mean=v[0], n=10, higher_is_better=v[1])
            for k, v in metrics.items()
        ],
        n_samples=10,
        judge_model="stub",
        timestamp="2026-05-06T00:00:00+00:00",
        duration_seconds=0.1,
        seed=0,
    )


def test_no_regression_when_unchanged() -> None:
    base = _report("a", faith=(0.8, True))
    cur = _report("a", faith=(0.8, True))
    r = diff_reports(base, cur, threshold_pp=5)
    assert not r.has_regressions
    assert r.deltas[0].status == "unchanged"


def test_regression_detected_above_threshold() -> None:
    base = _report("a", faith=(0.80, True))
    cur = _report("a", faith=(0.71, True))
    r = diff_reports(base, cur, threshold_pp=5)
    assert r.has_regressions
    assert r.regressions[0].name == "faith"
    assert r.deltas[0].status == "regression"


def test_no_regression_when_within_threshold() -> None:
    base = _report("a", faith=(0.80, True))
    cur = _report("a", faith=(0.78, True))
    r = diff_reports(base, cur, threshold_pp=5)
    assert not r.has_regressions


def test_lower_is_better_inverts_direction() -> None:
    base = _report("a", error_rate=(0.10, False))
    cur = _report("a", error_rate=(0.20, False))
    r = diff_reports(base, cur, threshold_pp=5)
    assert r.has_regressions


def test_added_and_removed_metrics_listed() -> None:
    base = _report("a", x=(0.5, True))
    cur = _report("a", y=(0.5, True))
    r = diff_reports(base, cur)
    assert "x" in r.removed
    assert "y" in r.added


def test_to_dict_serialisable() -> None:
    base = _report("a", x=(0.5, True))
    cur = _report("a", x=(0.4, True))
    d = diff_reports(base, cur, threshold_pp=5).to_dict()
    assert d["has_regressions"] is True
    assert d["deltas"][0]["name"] == "x"
