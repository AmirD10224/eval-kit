"""Suite YAML loader."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from evalkit.config import SuiteConfig
from evalkit.exceptions import ConfigError


def load_suite_config(path: str | Path) -> SuiteConfig:
    """Load and validate a suite YAML file into :class:`SuiteConfig`."""
    p = Path(path)
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{p}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{p}: suite must be a YAML mapping at the top level")
    try:
        return SuiteConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"{p}: suite validation failed:\n{exc}") from exc
