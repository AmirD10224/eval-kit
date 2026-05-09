"""Compare two suite reports and flag regressions over a configurable threshold.

The simple gate (``delta_pp < -threshold``) catches the obvious regressions.
We also compute a **paired bootstrap 95% CI** of the per-row delta when
both reports carry per-sample scores for the metric, that's the
statistically defensible signal under N=30-style sample sizes, where a 5pp
point-estimate move sits inside the noise envelope and naive thresholds
fire false positives.

A regression is *flagged* iff:

* the point estimate exceeds the threshold AND
* the 95% CI's "good-direction" bound also exceeds the threshold (i.e, the
  regression is statistically distinguishable from noise).

When per-sample data isn't available (e.g., legacy reports), we fall back
to the point-estimate threshold and set ``ci_*`` to ``None``, caller can
inspect ``MetricDelta.ci_*`` to see whether the verdict is statistically
backed.

Used by:

* ``evalkit diff --baseline a.json --current b.json``. CLI exit code 1.
* ``ci/github.py``, turns the diff into a Markdown PR comment.
* The GitHub Action's ``fail-on-regression`` input.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from evalkit.runner.report import SuiteReport

if TYPE_CHECKING:  # pragma: no cover
    from evalkit.runner.report import MetricResult


@dataclass(frozen=True, slots=True)
class MetricDelta:
    """Per-metric change between baseline and current."""

    name: str
    baseline: float
    current: float
    delta: float
    delta_pp: float  # percentage points (delta * 100)
    higher_is_better: bool
    is_regression: bool
    ci_low_pp: float | None = None  # lower 95% bound of delta_pp; None = no per-sample data
    ci_high_pp: float | None = None
    n_paired: int = 0  # paired sample count used for the CI

    @property
    def status(self) -> str:
        if self.is_regression:
            return "regression"
        if abs(self.delta_pp) < 0.5:
            return "unchanged"
        return "improvement"

    @property
    def stat_significant(self) -> bool:
        """True if the 95% CI excludes 0 (and we have per-sample data)."""
        if self.ci_low_pp is None or self.ci_high_pp is None:
            return False
        return self.ci_low_pp > 0 or self.ci_high_pp < 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "baseline": self.baseline,
            "current": self.current,
            "delta": self.delta,
            "delta_pp": self.delta_pp,
            "ci_low_pp": self.ci_low_pp,
            "ci_high_pp": self.ci_high_pp,
            "n_paired": self.n_paired,
            "higher_is_better": self.higher_is_better,
            "is_regression": self.is_regression,
            "stat_significant": self.stat_significant,
            "status": self.status,
        }


@dataclass(slots=True)
class RegressionReport:
    """The full diff. ``has_regressions`` short-circuits CI checks."""

    threshold_pp: float
    deltas: list[MetricDelta]
    added: list[str] = field(default_factory=list)  # metrics in current but not baseline
    removed: list[str] = field(default_factory=list)  # metrics in baseline but not current
    baseline_meta: dict[str, Any] = field(default_factory=dict)
    current_meta: dict[str, Any] = field(default_factory=dict)
    bootstrap_iterations: int = 0
    bootstrap_seed: int = 0

    @property
    def has_regressions(self) -> bool:
        return any(d.is_regression for d in self.deltas)

    @property
    def regressions(self) -> list[MetricDelta]:
        return [d for d in self.deltas if d.is_regression]

    def to_dict(self) -> dict[str, Any]:
        return {
            "threshold_pp": self.threshold_pp,
            "deltas": [d.to_dict() for d in self.deltas],
            "added": self.added,
            "removed": self.removed,
            "baseline_meta": self.baseline_meta,
            "current_meta": self.current_meta,
            "bootstrap_iterations": self.bootstrap_iterations,
            "bootstrap_seed": self.bootstrap_seed,
            "has_regressions": self.has_regressions,
        }


def diff_reports(
    baseline: SuiteReport,
    current: SuiteReport,
    *,
    threshold_pp: float = 5.0,
    bootstrap_iterations: int = 2000,
    bootstrap_seed: int = 0,
    require_significance: bool = True,
) -> RegressionReport:
    """Compute :class:`RegressionReport` for two suite reports.

    Args:
        baseline: the report we're comparing against (typically from ``main``).
        current: the report from the PR / current branch.
        threshold_pp: percentage-point gate. A metric is a *candidate*
            regression if the point estimate moves by more than this in the
            wrong direction.
        bootstrap_iterations: number of paired-bootstrap resamples used to
            compute the 95% CI on the delta. Set to 0 to skip the CI.
        bootstrap_seed: seed for reproducibility (deterministic CI).
        require_significance: when True (default), a candidate regression
            is only flagged if the 95% CI also crosses the threshold -
            i.e., the regression is distinguishable from noise. When per-
            sample data is unavailable, we fall back to the point gate.

    The metric direction is taken from ``current`` (a sign flip in
    ``higher_is_better`` between baseline and current is treated as a
    config error and ignored).
    """
    baseline_map = {m.name: m for m in baseline.metrics}
    current_map = {m.name: m for m in current.metrics}

    deltas: list[MetricDelta] = []
    for name in sorted(set(baseline_map) & set(current_map)):
        b = baseline_map[name]
        c = current_map[name]
        delta = c.mean - b.mean
        delta_pp = delta * 100.0

        ci_low_pp, ci_high_pp, n_paired = _paired_bootstrap_ci(
            b,
            c,
            iterations=bootstrap_iterations,
            seed=bootstrap_seed,
        )

        higher_is_better = bool(getattr(c, "higher_is_better", True))
        # Point-estimate gate.
        point_regression = delta_pp < -threshold_pp if higher_is_better else delta_pp > threshold_pp

        # Significance gate: the relevant CI bound also has to cross the threshold.
        if ci_low_pp is None or not require_significance:
            is_reg = point_regression
        elif higher_is_better:
            is_reg = point_regression and ci_high_pp is not None and ci_high_pp < -threshold_pp
        else:
            is_reg = point_regression and ci_low_pp is not None and ci_low_pp > threshold_pp

        deltas.append(
            MetricDelta(
                name=name,
                baseline=float(b.mean),
                current=float(c.mean),
                delta=delta,
                delta_pp=delta_pp,
                higher_is_better=higher_is_better,
                is_regression=is_reg,
                ci_low_pp=ci_low_pp,
                ci_high_pp=ci_high_pp,
                n_paired=n_paired,
            ),
        )

    return RegressionReport(
        threshold_pp=threshold_pp,
        deltas=deltas,
        added=sorted(set(current_map) - set(baseline_map)),
        removed=sorted(set(baseline_map) - set(current_map)),
        baseline_meta=_meta(baseline),
        current_meta=_meta(current),
        bootstrap_iterations=bootstrap_iterations,
        bootstrap_seed=bootstrap_seed,
    )


# ---- private --------------------------------------------------------------


def _paired_bootstrap_ci(
    baseline: MetricResult,
    current: MetricResult,
    *,
    iterations: int,
    seed: int,
    confidence: float = 0.95,
) -> tuple[float | None, float | None, int]:
    """Return ``(low_pp, high_pp, n_paired)`` for the per-row delta.

    Returns ``(None, None, 0)`` when either side lacks per-sample data or no
    rows can be paired by ``row_id``.
    """
    if iterations <= 0:
        return None, None, 0
    base_samples = {s.row_id: s.score for s in (baseline.samples or [])}
    cur_samples = {s.row_id: s.score for s in (current.samples or [])}
    if not base_samples or not cur_samples:
        return None, None, 0
    paired = [cur_samples[k] - base_samples[k] for k in base_samples.keys() & cur_samples.keys()]
    if len(paired) < 2:
        return None, None, len(paired)

    rng = random.Random(seed)
    n = len(paired)
    boot_means: list[float] = []
    for _ in range(iterations):
        resample_mean = sum(paired[rng.randint(0, n - 1)] for _ in range(n)) / n
        boot_means.append(resample_mean)
    boot_means.sort()
    alpha = (1.0 - confidence) / 2.0
    lo = boot_means[int(alpha * iterations)]
    hi = boot_means[min(iterations - 1, int((1.0 - alpha) * iterations))]
    return lo * 100.0, hi * 100.0, n


def _meta(report: SuiteReport) -> dict[str, Any]:
    return {
        "suite": report.suite_name,
        "git_sha": report.git_sha,
        "judge_model": report.judge_model,
        "timestamp": report.timestamp,
        "n_samples": report.n_samples,
    }
