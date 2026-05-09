"""LLM-as-judge primitives.

Public API:

* :class:`Rubric`, a YAML-loaded scoring spec.
* :class:`Judge`, protocol every judge satisfies.
* :class:`CalibratedJudge`, the production judge: rubric + bias audit +
  Cohen's kappa gate.
* :class:`CalibrationReport`, what :func:`CalibratedJudge.calibrate` returns.
"""

from evalkit.judges.base import Judge, JudgeOutput
from evalkit.judges.bias import BiasReport, audit_biases
from evalkit.judges.calibrated import CalibratedJudge, CalibrationReport
from evalkit.judges.rubric import Rubric
from evalkit.judges.stats import cohens_kappa, fleiss_kappa, krippendorff_alpha

__all__ = [
    "BiasReport",
    "CalibratedJudge",
    "CalibrationReport",
    "Judge",
    "JudgeOutput",
    "Rubric",
    "audit_biases",
    "cohens_kappa",
    "fleiss_kappa",
    "krippendorff_alpha",
]
