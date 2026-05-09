"""Shared pytest fixtures."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from evalkit.config import DatasetRow
from evalkit.dataset.store import GoldenDataset
from evalkit.judges.calibrated import CalibratedJudge
from evalkit.judges.rubric import Rubric
from evalkit.llm.stub import StubClient

# ----- minimal rubric fixture ----------------------------------------------


_RUBRIC_YAML = """\
name: faithfulness
description: Is the answer grounded in the provided context?
criteria:
  - name: grounded
    description: Every claim is supported by the context.
    scale: 5
  - name: no_invention
    description: No claims absent from the context.
    scale: 5
calibration:
  kappa_floor: 0.5
  min_samples: 10
  bias_threshold: 0.5
"""


@pytest.fixture
def rubric_yaml() -> str:
    return _RUBRIC_YAML


@pytest.fixture
def rubric(rubric_yaml: str) -> Rubric:
    return Rubric.from_text(rubric_yaml)


# ----- stub clients --------------------------------------------------------


def _scorer_mirroring_expected(prompt: str) -> dict[str, Any]:
    """Score per-criterion by reading whatever values appear in the prompt.

    The judge prompt contains the OUTPUT block as JSON. During ``CalibratedJudge.calibrate``
    that block carries the row's ``expected`` (because there's no live system),
    so we just regex-extract the per-criterion ints from anywhere in the prompt.
    Keeps the test deterministic without an API call.
    """
    grounded = _extract(prompt, "grounded", default=4)
    no_invention = _extract(prompt, "no_invention", default=4)
    return {"grounded": grounded, "no_invention": no_invention, "reasoning": "stub"}


def _extract(text: str, key: str, default: int) -> int:
    m = re.search(rf'"{key}"\s*:\s*(\d+)', text)
    return int(m.group(1)) if m else default


@pytest.fixture
def stub_client() -> StubClient:
    return StubClient(scorer=_scorer_mirroring_expected)


@pytest.fixture
def stub_client_constant_3() -> StubClient:
    """Always returns score=3 for every criterion."""
    return StubClient(default_response='{"grounded": 3, "no_invention": 3, "reasoning": "stub"}')


# ----- judge --------------------------------------------------------------


@pytest.fixture
def calibrated_judge(rubric: Rubric, stub_client: StubClient) -> CalibratedJudge:
    return CalibratedJudge(rubric=rubric, client=stub_client)


# ----- dataset fixtures ---------------------------------------------------


@pytest.fixture
def golden_rows() -> list[DatasetRow]:
    rows: list[DatasetRow] = []
    for i in range(20):
        rows.append(
            DatasetRow.model_validate(
                {
                    "id": f"row-{i:03d}",
                    "input": {"question": f"q{i}"},
                    "expected": {"grounded": (i % 5) + 1, "no_invention": (i % 5) + 1},
                    "labels": [
                        {"rater": "rater-1", "score": (i % 5) + 1},
                        {"rater": "rater-2", "score": (i % 5) + 1},
                    ],
                },
            ),
        )
    return rows


@pytest.fixture
def golden_dataset(golden_rows: list[DatasetRow]) -> GoldenDataset:
    return GoldenDataset(golden_rows)


@pytest.fixture
def golden_path(tmp_path: Path, golden_dataset: GoldenDataset) -> Path:
    p = tmp_path / "golden.jsonl"
    golden_dataset.save(p)
    return p


# ----- prediction fixtures ------------------------------------------------


@pytest.fixture
def predictions_path(tmp_path: Path, golden_rows: list[DatasetRow]) -> Path:
    p = tmp_path / "predictions.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for row in golden_rows:
            f.write(
                json.dumps(
                    {
                        "id": row.id,
                        "output": dict(row.expected or {}),
                    },
                ),
            )
            f.write("\n")
    return p


# ----- yield a temp working dir ------------------------------------------


@pytest.fixture
def cwd_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.chdir(tmp_path)
    return tmp_path
