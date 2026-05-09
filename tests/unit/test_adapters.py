"""Adapter tests, focus on the import-error paths and promptfoo conversion."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from evalkit.adapters.promptfoo import import_promptfoo_config
from evalkit.exceptions import AdapterError, ConfigError


def test_promptfoo_minimal(tmp_path: Path) -> None:
    cfg = tmp_path / "promptfooconfig.yaml"
    cfg.write_text(
        """
description: hello
tests:
  - vars:
      question: What is 2+2?
    assert:
      - type: contains
        value: "4"
""",
    )
    suite, rows = import_promptfoo_config(cfg)
    assert suite.name == "hello"
    assert len(rows) == 1
    assert rows[0].input["question"] == "What is 2+2?"
    metric_kinds = {m.kind for m in suite.metrics}
    assert "regex" in metric_kinds


def test_promptfoo_falls_back_to_judge_when_no_assertions(tmp_path: Path) -> None:
    cfg = tmp_path / "p.yaml"
    cfg.write_text(
        """
tests:
  - vars: {q: x}
""",
    )
    suite, _ = import_promptfoo_config(cfg)
    assert suite.metrics[0].kind == "judge"


def test_promptfoo_handles_equals(tmp_path: Path) -> None:
    cfg = tmp_path / "p.yaml"
    cfg.write_text(
        """
tests:
  - vars: {q: x}
    assert:
      - type: equals
        value: y
""",
    )
    suite, _ = import_promptfoo_config(cfg)
    assert any(m.kind == "exact_match" for m in suite.metrics)


def test_promptfoo_handles_llm_rubric(tmp_path: Path) -> None:
    cfg = tmp_path / "p.yaml"
    cfg.write_text(
        """
tests:
  - vars: {q: x}
    assert:
      - type: llm-rubric
""",
    )
    suite, _ = import_promptfoo_config(cfg)
    assert any(m.kind == "judge" for m in suite.metrics)


def test_promptfoo_invalid_top_level_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("- a\n- b\n")
    with pytest.raises(ConfigError, match="mapping"):
        import_promptfoo_config(cfg)


def test_promptfoo_no_tests_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "no.yaml"
    cfg.write_text("description: x\n")
    with pytest.raises(ConfigError, match="tests"):
        import_promptfoo_config(cfg)


def test_promptfoo_skips_non_dict_test_entries(tmp_path: Path) -> None:
    cfg = tmp_path / "p.yaml"
    cfg.write_text(
        """
tests:
  - vars: {q: x}
  - just a string
""",
    )
    with pytest.warns(UserWarning):
        suite, rows = import_promptfoo_config(cfg)
    assert len(rows) == 1


# ---------- ragas adapter ------------------------------------------------


def test_ragas_unsupported_metric() -> None:
    from evalkit.adapters.ragas import RagasScorer

    with pytest.raises(AdapterError, match="unsupported"):
        RagasScorer("not_a_metric")


def test_ragas_missing_dep(monkeypatch: pytest.MonkeyPatch) -> None:
    """If ragas isn't installed, the constructor surfaces a friendly error."""
    monkeypatch.setitem(sys.modules, "ragas", None)
    monkeypatch.setitem(sys.modules, "ragas.metrics", None)
    from evalkit.adapters.ragas import RagasScorer

    with pytest.raises(AdapterError, match="ragas not installed"):
        RagasScorer("faithfulness")


# ---------- langfuse adapter ---------------------------------------------


def test_langfuse_pull_traces_missing_dep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "langfuse", None)
    from evalkit.adapters.langfuse import pull_traces

    with pytest.raises(AdapterError, match="langfuse not installed"):
        pull_traces()


def test_langfuse_push_score_missing_dep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "langfuse", None)
    from evalkit.adapters.langfuse import push_score

    with pytest.raises(AdapterError, match="langfuse not installed"):
        push_score(trace_id="x", name="y", value=0.0)


def test_langfuse_with_fake_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a fake langfuse module so we can exercise the happy path."""

    class _FakeTrace:
        def __init__(self, idx: int) -> None:
            self.id = f"trace-{idx}"
            self.input = {"q": idx}
            self.output = {"a": idx}
            self.session_id = None
            self.user_id = None
            self.name = "demo"
            self.tags = ["t1"]

    class _FakeResponse:
        def __init__(self, n: int = 2) -> None:
            self.data = [_FakeTrace(i) for i in range(n)]

    class _FakeLangfuse:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def fetch_traces(self, **_kwargs: Any) -> _FakeResponse:
            return _FakeResponse()

        def score(self, **_kwargs: Any) -> None:
            pass

    fake_module = type(sys)("langfuse")
    fake_module.Langfuse = _FakeLangfuse  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langfuse", fake_module)

    from evalkit.adapters.langfuse import pull_traces, push_score

    rows = pull_traces(limit=2)
    assert len(rows) == 2
    assert rows[0]["id"] == "trace-0"
    push_score(trace_id="x", name="y", value=0.5)


# ---------- braintrust adapter -------------------------------------------


def test_braintrust_missing_dep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "braintrust", None)
    from evalkit.adapters.braintrust import push_report
    from evalkit.runner.report import MetricResult, SuiteReport

    rep = SuiteReport(
        suite_name="x",
        metrics=[MetricResult(name="m", kind="judge", mean=0.5, n=1)],
        n_samples=1,
        judge_model="x",
        timestamp="2026-05-06T00:00:00+00:00",
        duration_seconds=0.1,
        seed=0,
    )
    with pytest.raises(AdapterError, match="braintrust"):
        push_report(rep, project="p")


def test_braintrust_with_fake_module(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = type(sys)("braintrust")
    exp = MagicMock()
    summary = MagicMock(experiment_url="https://braintrust.dev/x")
    exp.summarize.return_value = summary
    fake.init = MagicMock(return_value=exp)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "braintrust", fake)

    from evalkit.adapters.braintrust import push_report
    from evalkit.runner.report import MetricResult, Sample, SuiteReport

    rep = SuiteReport(
        suite_name="x",
        metrics=[
            MetricResult(
                name="m",
                kind="judge",
                mean=0.5,
                n=1,
                samples=[Sample(row_id="a", score=0.5, detail={})],
            ),
        ],
        n_samples=1,
        judge_model="x",
        timestamp="2026-05-06T00:00:00+00:00",
        duration_seconds=0.1,
        seed=0,
    )
    url = push_report(rep, project="p")
    assert url == "https://braintrust.dev/x"


# ---------- inspect_ai adapter -------------------------------------------


def test_inspect_ai_missing_dep(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setitem(sys.modules, "inspect_ai", None)
    from evalkit.adapters.inspect_ai import to_inspect_task
    from evalkit.config import SuiteConfig

    suite = SuiteConfig.model_validate(
        {
            "name": "x",
            "dataset": "d.jsonl",
            "metrics": [{"name": "m", "kind": "exact_match"}],
        },
    )
    with pytest.raises(AdapterError, match="inspect-ai"):
        to_inspect_task(suite, tmp_path)
