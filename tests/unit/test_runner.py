"""Runner / suite tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evalkit.exceptions import ConfigError, EvalKitError
from evalkit.llm.stub import StubClient
from evalkit.runner.report import MetricResult, Sample, SuiteReport
from evalkit.runner.runner import Suite


@pytest.fixture
def suite_yaml(tmp_path: Path, golden_path: Path) -> Path:
    rubric_path = tmp_path / "rub.yaml"
    rubric_path.write_text(
        "name: faithfulness\n"
        "description: y\n"
        "criteria:\n"
        "  - name: grounded\n    description: g\n    scale: 5\n"
        "  - name: no_invention\n    description: n\n    scale: 5\n"
        "calibration:\n  kappa_floor: 0.5\n  min_samples: 10\n  bias_threshold: 0.5\n",
    )
    suite_path = tmp_path / "suite.yaml"
    suite_path.write_text(
        f"""
name: demo
description: demo suite
dataset: {golden_path.name}
metrics:
  - name: judge_score
    kind: judge
    rubric: {rubric_path.name}
    target: 0.5
  - name: regex_yes
    kind: regex
    pattern: "^.+$"
  - name: exact
    kind: exact_match
parallelism: 4
seed: 7
""",
    )
    # Move golden into same dir as suite so relative paths resolve
    (tmp_path / golden_path.name).write_bytes(golden_path.read_bytes())
    return suite_path


def test_run_suite_self_predictions(suite_yaml: Path) -> None:
    client = StubClient(default_response='{"grounded": 5, "no_invention": 5}')
    suite = Suite.from_yaml(suite_yaml)
    result = suite.run(client=client)
    assert result.report.suite_name == "demo"
    metric_names = {m.name for m in result.report.metrics}
    assert metric_names == {"judge_score", "regex_yes", "exact"}


def test_run_suite_with_predictions(
    suite_yaml: Path,
    predictions_path: Path,
    tmp_path: Path,
) -> None:
    # Copy predictions next to the suite
    pred_in_suite_dir = tmp_path / predictions_path.name
    pred_in_suite_dir.write_bytes(predictions_path.read_bytes())
    client = StubClient(default_response='{"grounded": 5, "no_invention": 5}')
    suite = Suite.from_yaml(suite_yaml)
    result = suite.run(client=client, predictions=pred_in_suite_dir)
    assert result.report.n_samples == 20


def test_run_saves_report(tmp_path: Path, suite_yaml: Path) -> None:
    client = StubClient(default_response='{"grounded": 5, "no_invention": 5}')
    suite = Suite.from_yaml(suite_yaml)
    result = suite.run(client=client)
    out = tmp_path / "report.json"
    result.save(out)
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["suite"] == "demo"
    assert data["seed"] == 7


def test_predictions_missing_for_id_raises(suite_yaml: Path, tmp_path: Path) -> None:
    bad_pred = tmp_path / "bad.jsonl"
    bad_pred.write_text('{"id": "missing", "output": {}}\n')
    suite = Suite.from_yaml(suite_yaml)
    client = StubClient(default_response='{"grounded": 5, "no_invention": 5}')
    with pytest.raises(EvalKitError, match="missing"):
        suite.run(client=client, predictions=bad_pred)


def test_invalid_prediction_row(tmp_path: Path, suite_yaml: Path) -> None:
    bad_pred = tmp_path / "bad.jsonl"
    bad_pred.write_text("not-json\n")
    suite = Suite.from_yaml(suite_yaml)
    with pytest.raises(EvalKitError, match="invalid"):
        suite.run(client=StubClient(), predictions=bad_pred)


def test_duplicate_prediction_id(tmp_path: Path, suite_yaml: Path) -> None:
    bad_pred = tmp_path / "dup.jsonl"
    bad_pred.write_text(
        '{"id": "row-000", "output": {}}\n{"id": "row-000", "output": {}}\n',
    )
    with pytest.raises(EvalKitError, match="duplicate"):
        Suite.from_yaml(suite_yaml).run(client=StubClient(), predictions=bad_pred)


def test_unknown_kind_raises(tmp_path: Path, golden_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text(
        f"""
name: bad
dataset: {golden_path.name}
metrics:
  - name: m
    kind: weird
""",
    )
    (tmp_path / golden_path.name).write_bytes(golden_path.read_bytes())
    with pytest.raises(ConfigError):
        Suite.from_yaml(p)


def test_judge_kind_requires_rubric(tmp_path: Path, golden_path: Path) -> None:
    p = tmp_path / "no_rub.yaml"
    p.write_text(
        f"""
name: x
dataset: {golden_path.name}
metrics:
  - name: m
    kind: judge
""",
    )
    (tmp_path / golden_path.name).write_bytes(golden_path.read_bytes())
    suite = Suite.from_yaml(p)
    with pytest.raises(ConfigError, match="rubric"):
        suite.run(client=StubClient())


def test_custom_scorer_must_be_registered(tmp_path: Path, golden_path: Path) -> None:
    p = tmp_path / "custom.yaml"
    p.write_text(
        f"""
name: x
dataset: {golden_path.name}
metrics:
  - name: my_custom
    kind: custom
""",
    )
    (tmp_path / golden_path.name).write_bytes(golden_path.read_bytes())
    suite = Suite.from_yaml(p)
    with pytest.raises(ConfigError, match="register_scorer"):
        suite.run(client=StubClient())


def test_custom_scorer_runs_when_registered(tmp_path: Path, golden_path: Path) -> None:
    p = tmp_path / "custom.yaml"
    p.write_text(
        f"""
name: x
dataset: {golden_path.name}
metrics:
  - name: my_custom
    kind: custom
""",
    )
    (tmp_path / golden_path.name).write_bytes(golden_path.read_bytes())
    suite = Suite.from_yaml(p)
    suite.register_scorer(
        "my_custom",
        lambda _i, _o, _e: 0.42,
    )
    result = suite.run(client=StubClient())
    assert result.report.metrics[0].mean == pytest.approx(0.42)


# ---------- report serialisation ------------------------------------------


def test_report_roundtrip(tmp_path: Path) -> None:
    rep = SuiteReport(
        suite_name="x",
        metrics=[
            MetricResult(
                name="m",
                kind="judge",
                mean=0.7,
                n=2,
                samples=[Sample(row_id="a", score=0.7, detail={})],
            ),
        ],
        n_samples=1,
        judge_model="stub",
        timestamp="2026-05-06T00:00:00+00:00",
        duration_seconds=1.0,
        seed=0,
    )
    out = tmp_path / "r.json"
    rep.save(out)
    loaded = SuiteReport.load(out)
    assert loaded.metrics[0].name == "m"
    assert loaded.metrics[0].mean == pytest.approx(0.7)


def test_metric_passes_target() -> None:
    m = MetricResult(name="m", kind="judge", mean=0.8, n=1, target=0.5)
    assert m.passes_target()
    m2 = MetricResult(name="m", kind="judge", mean=0.4, n=1, target=0.5)
    assert not m2.passes_target()
    m3 = MetricResult(name="m", kind="judge", mean=0.4, n=1, target=0.5, higher_is_better=False)
    assert m3.passes_target()
    m4 = MetricResult(name="m", kind="judge", mean=0.4, n=1)
    assert m4.passes_target()


def test_render_does_not_raise(suite_yaml: Path) -> None:
    client = StubClient(default_response='{"grounded": 5, "no_invention": 5}')
    suite = Suite.from_yaml(suite_yaml)
    suite.run(client=client).render()
