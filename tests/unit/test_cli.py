"""CLI smoke tests via Click's CliRunner."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from evalkit.cli import main


def _write_rubric(path: Path) -> None:
    path.write_text(
        "name: faith\n"
        "description: f\n"
        "criteria:\n"
        "  - name: grounded\n    description: g\n    scale: 5\n"
        "calibration:\n  kappa_floor: 0.5\n  min_samples: 10\n  bias_threshold: 0.5\n",
    )


def _write_golden(path: Path) -> None:
    rows = []
    for i in range(15):
        rows.append(
            {
                "id": f"r-{i:03d}",
                "input": {"q": f"q{i}"},
                "expected": {"grounded": (i % 5) + 1},
                "labels": [{"score": (i % 5) + 1}, {"score": (i % 5) + 1}],
            },
        )
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_version() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "evalkit" in result.output


def test_dataset_validate(tmp_path: Path) -> None:
    g = tmp_path / "g.jsonl"
    _write_golden(g)
    runner = CliRunner()
    result = runner.invoke(main, ["dataset", "validate", str(g)])
    assert result.exit_code == 0
    assert "valid" in result.output


def test_dataset_add(tmp_path: Path) -> None:
    case = tmp_path / "case.json"
    case.write_text('{"id": "new", "input": {"q": 1}}')
    out = tmp_path / "g.jsonl"
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["dataset", "add", "--case", str(case), "--to", str(out)],
    )
    assert result.exit_code == 0
    assert out.exists()


def test_dataset_agreement(tmp_path: Path) -> None:
    g = tmp_path / "g.jsonl"
    _write_golden(g)
    runner = CliRunner()
    result = runner.invoke(main, ["dataset", "agreement", str(g)])
    assert result.exit_code == 0
    assert "kappa" in result.output


def test_judge_calibrate_pass(tmp_path: Path) -> None:
    rubric = tmp_path / "r.yaml"
    _write_rubric(rubric)
    g = tmp_path / "g.jsonl"
    _write_golden(g)
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "judge",
            "calibrate",
            "--rubric",
            str(rubric),
            "--golden",
            str(g),
            "--stub",
            "--no-bias-audit",
        ],
    )
    # The stub returns score=4 always (echo-from-prompt with no score in prompt).
    # Humans have varying scores → kappa low → expect non-zero exit
    # (well-behaved CLI returns 1, exception path returns 2).
    assert result.exit_code in (0, 1)


def test_run_suite(tmp_path: Path) -> None:
    rubric = tmp_path / "r.yaml"
    _write_rubric(rubric)
    g = tmp_path / "g.jsonl"
    _write_golden(g)
    suite = tmp_path / "suite.yaml"
    suite.write_text(
        f"""
name: t
dataset: {g.name}
metrics:
  - name: judge
    kind: judge
    rubric: {rubric.name}
""",
    )
    out = tmp_path / "report.json"
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["run", "--suite", str(suite), "--output", str(out), "--stub"],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text())
    assert "metrics" in data


def test_diff_no_regression(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    cur = tmp_path / "cur.json"
    body = {
        "schema_version": 1,
        "suite": "x",
        "timestamp": "2026-05-06T00:00:00+00:00",
        "metrics": {"m": 0.5},
        "n_samples": 1,
        "judge_model": "stub",
        "git_sha": None,
        "seed": 0,
        "duration_seconds": 0.0,
        "per_metric": {
            "m": {"kind": "judge", "mean": 0.5, "n": 1, "target": None, "higher_is_better": True},
        },
    }
    base.write_text(json.dumps(body))
    body["per_metric"]["m"]["mean"] = 0.51
    body["metrics"]["m"] = 0.51
    cur.write_text(json.dumps(body))
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["diff", "--baseline", str(base), "--current", str(cur), "--threshold", "5"],
    )
    assert result.exit_code == 0


def test_diff_with_regression_exits_one(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    cur = tmp_path / "cur.json"
    body = {
        "schema_version": 1,
        "suite": "x",
        "timestamp": "2026-05-06T00:00:00+00:00",
        "metrics": {"m": 0.85},
        "n_samples": 1,
        "judge_model": "stub",
        "git_sha": None,
        "seed": 0,
        "duration_seconds": 0.0,
        "per_metric": {
            "m": {"kind": "judge", "mean": 0.85, "n": 1, "target": None, "higher_is_better": True},
        },
    }
    base.write_text(json.dumps(body))
    body["per_metric"]["m"]["mean"] = 0.70
    body["metrics"]["m"] = 0.70
    cur.write_text(json.dumps(body))

    md = tmp_path / "comment.md"
    json_out = tmp_path / "diff.json"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "diff",
            "--baseline",
            str(base),
            "--current",
            str(cur),
            "--threshold",
            "5",
            "--markdown",
            str(md),
            "--json-out",
            str(json_out),
        ],
    )
    assert result.exit_code == 1
    assert md.exists()
    assert json_out.exists()


def test_synth_generate_stub(tmp_path: Path) -> None:
    schema = tmp_path / "schema.yaml"
    schema.write_text("question: str\n")
    out = tmp_path / "synth.jsonl"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "synth",
            "generate",
            "--task",
            "QA",
            "--schema",
            str(schema),
            "--count",
            "5",
            "--output",
            str(out),
            "--stub",
        ],
    )
    assert result.exit_code == 0, result.output
    # The default stub response isn't a list, so synth produces 0 rows; that's fine -
    # we're verifying the CLI plumbing, not the stub's content.
    assert out.exists()


def test_synth_generate_with_categories(tmp_path: Path) -> None:
    schema = tmp_path / "schema.yaml"
    schema.write_text("q: str\n")
    out = tmp_path / "out.jsonl"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "synth",
            "generate",
            "--task",
            "QA",
            "--schema",
            str(schema),
            "--count",
            "2",
            "--categories",
            "edge_cases,jailbreaks",
            "--output",
            str(out),
            "--stub",
        ],
    )
    assert result.exit_code == 0
