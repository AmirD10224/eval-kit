"""YAML rubric loader and prompt-render helpers.

A rubric is a structured scoring spec used by :class:`CalibratedJudge`. We
keep the prompt-rendering logic right next to the rubric so changing the
rubric format and the prompt happen in lockstep.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import ValidationError

from evalkit.config import RubricConfig
from evalkit.exceptions import ConfigError

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping


_SYSTEM_TMPL = (
    "You are a strict, calibrated evaluator. Score the candidate response on the "
    "rubric below. Output STRICT JSON ONLY, no prose, no markdown.\n\n"
    "Rubric: {name}\n{description}\n\n"
    "Criteria:\n{criteria_list}\n\n"
    "Output schema (JSON object with one numeric score per criterion):\n{schema}"
)

_USER_TMPL = (
    "INPUT:\n{input}\n\n"
    "EXPECTED (may be empty):\n{expected}\n\n"
    "CANDIDATE OUTPUT:\n{output}\n\n"
    "Score using the rubric. Return JSON only."
)


class Rubric:
    """A loaded, validated rubric ready to render judge prompts."""

    def __init__(self, config: RubricConfig) -> None:
        self.config = config

    # ---------- loaders ------------------------------------------------

    @classmethod
    def from_yaml(cls, path: str | Path) -> Rubric:
        """Load a rubric from a YAML file path."""
        text = Path(path).read_text(encoding="utf-8")
        return cls.from_text(text, source=str(path))

    @classmethod
    def from_text(cls, text: str, *, source: str = "<inline>") -> Rubric:
        """Load a rubric from a YAML or JSON string."""
        try:
            raw = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"{source}: invalid YAML: {exc}") from exc
        if not isinstance(raw, dict):
            raise ConfigError(f"{source}: rubric must be a YAML mapping at the top level")
        try:
            config = RubricConfig.model_validate(raw)
        except ValidationError as exc:
            raise ConfigError(f"{source}: rubric validation failed:\n{exc}") from exc
        return cls(config)

    # ---------- prompt rendering --------------------------------------

    def render_system(self) -> str:
        criteria_lines = []
        for c in self.config.criteria:
            anchor_str = (
                ""
                if not c.anchors
                else "\n      anchors: "
                + ", ".join(f"{k}={v!r}" for k, v in sorted(c.anchors.items()))
            )
            criteria_lines.append(
                f"  - {c.name} (1..{c.scale}, weight {c.weight}): {c.description}{anchor_str}",
            )
        schema = json.dumps(
            {c.name: f"<int 1..{c.scale}>" for c in self.config.criteria},
            indent=2,
        )
        return _SYSTEM_TMPL.format(
            name=self.config.name,
            description=self.config.description,
            criteria_list="\n".join(criteria_lines),
            schema=schema,
        )

    def render_user(
        self,
        *,
        input_data: Mapping[str, Any],
        output_data: Mapping[str, Any],
        expected: Mapping[str, Any] | None = None,
    ) -> str:
        return _USER_TMPL.format(
            input=json.dumps(input_data, indent=2, default=str),
            expected=json.dumps(expected or {}, indent=2, default=str),
            output=json.dumps(output_data, indent=2, default=str),
        )

    # ---------- scoring helpers ---------------------------------------

    def aggregate(self, criterion_scores: Mapping[str, float]) -> float:
        """Combine per-criterion scores into a single weighted, normalised score in [0, 1]."""
        total_weight = sum(c.weight for c in self.config.criteria)
        if total_weight == 0:
            return 0.0
        weighted_sum = 0.0
        for c in self.config.criteria:
            raw = float(criterion_scores.get(c.name, 1))
            normalised = (raw - 1) / (c.scale - 1) if c.scale > 1 else 0.0
            weighted_sum += normalised * c.weight
        return weighted_sum / total_weight

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def criterion_names(self) -> list[str]:
        return [c.name for c in self.config.criteria]
