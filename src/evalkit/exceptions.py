"""All EvalKit exceptions inherit from a single root for easy catch-all."""

from __future__ import annotations


class EvalKitError(Exception):
    """Root for every error raised by EvalKit."""


class ConfigError(EvalKitError):
    """Raised when a YAML/JSON config or rubric fails validation."""


class DatasetError(EvalKitError):
    """Raised when a golden dataset is malformed or fails schema validation."""


class JudgeError(EvalKitError):
    """Raised when a judge cannot score (e.g., LLM response unparseable)."""


class CalibrationFailure(JudgeError):
    """Raised when calibration falls below the configured kappa floor.

    Carries the achieved kappa so callers can show a useful error.
    """

    def __init__(self, kappa: float, floor: float, detail: str = "") -> None:
        self.kappa = kappa
        self.floor = floor
        msg = f"calibration kappa={kappa:.3f} below floor={floor:.3f}"
        if detail:
            msg = f"{msg}: {detail}"
        super().__init__(msg)


class BiasDetected(JudgeError):
    """Raised when a bias audit flags a judge as unreliable for production."""

    def __init__(self, kind: str, magnitude: float, threshold: float) -> None:
        self.kind = kind
        self.magnitude = magnitude
        self.threshold = threshold
        super().__init__(
            f"{kind} bias of {magnitude:.3f} exceeds threshold {threshold:.3f}",
        )


class RegressionFailure(EvalKitError):
    """Raised by the GitHub Action / CLI when regressions exceed the threshold."""


class AdapterError(EvalKitError):
    """Raised when an optional integration (Ragas, Langfuse, …) is missing or misused."""
