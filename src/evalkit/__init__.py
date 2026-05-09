"""EvalKit, production-grade eval harness for LLM apps.

Public API surface:

    from evalkit import (
        Suite, SuiteResult, Sample, MetricResult,
        CalibratedJudge, Rubric, CalibrationReport,
        GoldenDataset, RegressionReport,
        SynthGenerator, Taxonomy,
    )

Everything else (adapters, CLI internals, render helpers) is considered
internal; submodules are imported explicitly when needed.
"""

from evalkit._version import __version__
from evalkit.dataset.store import GoldenDataset
from evalkit.diff.differ import RegressionReport
from evalkit.judges.calibrated import CalibratedJudge, CalibrationReport
from evalkit.judges.rubric import Rubric
from evalkit.runner.report import MetricResult, Sample
from evalkit.runner.runner import Suite, SuiteResult
from evalkit.synth.generator import SynthGenerator
from evalkit.synth.taxonomy import Taxonomy

__all__ = [
    "CalibratedJudge",
    "CalibrationReport",
    "GoldenDataset",
    "MetricResult",
    "RegressionReport",
    "Rubric",
    "Sample",
    "Suite",
    "SuiteResult",
    "SynthGenerator",
    "Taxonomy",
    "__version__",
]
