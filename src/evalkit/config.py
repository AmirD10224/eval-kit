"""Pydantic v2 strict models for everything that crosses the user boundary.

These types are the *contract*. YAML rubrics, suite files, dataset rows, and
the JSON report schema all parse through these models. Everything is
``model_config = ConfigDict(extra="forbid", strict=True)`` so a typo in a
YAML key fails loudly instead of being silently dropped.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------- Common ----------------------------------------------------------

_STRICT = ConfigDict(extra="forbid", strict=True, frozen=True)


class _Strict(BaseModel):
    model_config = _STRICT


# ---------- Calibration / Rubric --------------------------------------------


class CalibrationConfig(_Strict):
    """Calibration thresholds applied during ``CalibratedJudge.calibrate``."""

    kappa_floor: Annotated[float, Field(ge=0.0, le=1.0)] = 0.7
    min_samples: Annotated[int, Field(ge=10)] = 30
    bias_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = 0.15


class RubricCriterion(_Strict):
    """A single named criterion the judge will score on a 1..N scale."""

    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1)
    scale: Annotated[int, Field(ge=2, le=10)] = 5
    weight: Annotated[float, Field(ge=0.0, le=10.0)] = 1.0
    anchors: dict[int, str] = Field(default_factory=dict)


class RubricConfig(_Strict):
    """The schema of a YAML rubric file.

    Example::

        name: faithfulness
        description: Does the answer cite content actually present in the context?
        criteria:
          - name: grounded
            description: Every claim is supported by the provided context.
            scale: 5
          - name: no_invention
            description: No facts not present in the context.
            scale: 5
        calibration:
          kappa_floor: 0.7
          min_samples: 30
    """

    name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1)
    criteria: list[RubricCriterion] = Field(min_length=1)
    calibration: CalibrationConfig = Field(default_factory=CalibrationConfig)

    @model_validator(mode="after")
    def _at_least_one_nonzero_weight(self) -> RubricConfig:
        if all(c.weight == 0.0 for c in self.criteria):
            raise ValueError(
                "rubric must have at least one criterion with non-zero weight; "
                "otherwise the aggregate score collapses to 0.0",
            )
        return self


# ---------- Suite (eval runner config) --------------------------------------


_METRIC_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-:/ ]{1,64}$")
_REGEX_MAX_LEN = 256


class MetricSpec(_Strict):
    """A single metric to compute in an eval suite.

    The character whitelist on ``name`` is deliberate: the name is rendered
    verbatim into the GitHub-PR-comment Markdown, so it must not contain
    backticks, pipes, brackets, or newlines that could break out of the
    table or smuggle clickable links.
    """

    name: str = Field(min_length=1, max_length=64)
    kind: Literal["judge", "ragas", "exact_match", "regex", "custom"]
    rubric: str | None = None  # path, only for kind="judge"
    metric: str | None = None  # ragas metric name, only for kind="ragas"
    pattern: str | None = None  # only for kind="regex"
    target: float | None = None  # gate threshold (informational)
    higher_is_better: bool = True

    @field_validator("name")
    @classmethod
    def _safe_name(cls, v: str) -> str:
        if not _METRIC_NAME_RE.fullmatch(v):
            raise ValueError(
                f"metric name {v!r} must match {_METRIC_NAME_RE.pattern}. "
                "name is rendered into Markdown PR comments and must not contain "
                "backticks, pipes, brackets, or other markdown-active characters.",
            )
        return v

    @field_validator("pattern")
    @classmethod
    def _bounded_pattern(cls, v: str | None) -> str | None:
        if v is not None and len(v) > _REGEX_MAX_LEN:
            raise ValueError(
                f"regex pattern length {len(v)} exceeds limit ({_REGEX_MAX_LEN}); "
                "trim or pre-compute the metric.",
            )
        return v


class SuiteConfig(_Strict):
    """The schema of a YAML suite file."""

    name: str
    description: str = ""
    dataset: str  # path to a golden JSONL
    predictions: str | None = None  # path to a predictions JSONL
    metrics: list[MetricSpec] = Field(min_length=1)
    parallelism: Annotated[int, Field(ge=1, le=64)] = 8
    judge_model: str = "claude-haiku-4-5-20251001"
    seed: Annotated[int, Field(ge=0)] = 42


# ---------- Dataset rows ----------------------------------------------------


class DatasetRow(_Strict):
    """One row of a golden dataset (JSONL)."""

    id: str = Field(min_length=1)
    input: Mapping[str, Any]
    expected: Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] = Field(default_factory=dict)
    labels: list[Mapping[str, Any]] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id_no_whitespace(cls, v: str) -> str:
        if any(c.isspace() for c in v):
            raise ValueError("dataset row id must not contain whitespace")
        return v


class PredictionRow(_Strict):
    """One row of a predictions JSONL: what the system under test produced."""

    id: str = Field(min_length=1)
    output: Mapping[str, Any]
    metadata: Mapping[str, Any] = Field(default_factory=dict)


# ---------- Report ----------------------------------------------------------


class ReportEnvelope(_Strict):
    """Top-level JSON report written by ``evalkit run``.

    Versioned so future readers can branch on schema_version.
    """

    schema_version: Literal[1] = 1
    suite: str
    timestamp: str  # ISO-8601 UTC
    metrics: dict[str, float]
    n_samples: int
    judge_model: str
    git_sha: str | None = None
    seed: int
    duration_seconds: float
