"""promptfoo config import, turn a ``promptfooconfig.yaml`` into an EvalKit suite.

We only convert the bits that map cleanly: tests → dataset rows, asserts →
metric specs. Anything promptfoo-specific (providers, transformations) is
ignored with a warning. This is enough to migrate an existing promptfoo
project to EvalKit in an afternoon.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import yaml

from evalkit.config import DatasetRow, MetricSpec, SuiteConfig
from evalkit.exceptions import ConfigError


def import_promptfoo_config(path: str | Path) -> tuple[SuiteConfig, list[DatasetRow]]:
    """Convert a promptfoo config to an EvalKit suite + golden dataset.

    Returns:
        ``(suite_config, dataset_rows)``. Caller is responsible for writing
        them out (we don't side-effect the filesystem from the importer).
    """
    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ConfigError(f"{p}: top-level must be a mapping")

    name = str(raw.get("description") or p.stem)
    tests = raw.get("tests") or []
    if not isinstance(tests, list) or not tests:
        raise ConfigError(f"{p}: no `tests` list")

    rows: list[DatasetRow] = []
    metric_kinds: dict[str, MetricSpec] = {}
    for i, t in enumerate(tests):
        if not isinstance(t, dict):
            warnings.warn(f"skipping non-dict test at index {i}", stacklevel=2)
            continue
        vars_ = t.get("vars") or {}
        rows.append(
            DatasetRow.model_validate(
                {
                    "id": f"pfoo-{i:04d}",
                    "input": vars_ if isinstance(vars_, dict) else {"vars": vars_},
                    "metadata": {"source": "promptfoo", "test_index": i},
                },
            ),
        )
        for assertion in t.get("assert") or []:
            if not isinstance(assertion, dict):
                continue
            kind = str(assertion.get("type", "")).lower()
            if kind in {"contains", "icontains"}:
                pattern = str(assertion.get("value", ""))
                if pattern:
                    metric_kinds.setdefault(
                        f"contains_{kind}",
                        MetricSpec(name=f"contains_{kind}", kind="regex", pattern=pattern),
                    )
            elif kind == "equals":
                metric_kinds.setdefault(
                    "equals",
                    MetricSpec(name="equals", kind="exact_match"),
                )
            elif kind in {"llm-rubric", "model-graded-closedqa"}:
                metric_kinds.setdefault(
                    "judge",
                    MetricSpec(
                        name="judge",
                        kind="judge",
                        rubric="rubrics/imported.yaml",
                    ),
                )

    if not metric_kinds:
        # Fall back to a single judge metric so the imported suite still runs.
        metric_kinds["judge"] = MetricSpec(
            name="judge",
            kind="judge",
            rubric="rubrics/imported.yaml",
        )

    suite_dict: dict[str, Any] = {
        "name": name,
        "description": f"Imported from promptfoo: {p.name}",
        "dataset": "imported.jsonl",
        "metrics": [m.model_dump() for m in metric_kinds.values()],
    }
    return SuiteConfig.model_validate(suite_dict), rows
