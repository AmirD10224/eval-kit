"""Inter-rater agreement statistics.

We implement Cohen's kappa, Fleiss' kappa, and Krippendorff's alpha by hand
(small functions, easy to test) instead of taking a dep on scikit-learn or
statsmodels just for these three formulas.

References:
    * Cohen, J. (1960). A coefficient of agreement for nominal scales.
    * Fleiss, J. L. (1971). Measuring nominal scale agreement among many raters.
    * Krippendorff, K. (2004). Content analysis: An introduction.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any, TypeVar

import numpy as np

T = TypeVar("T", int, str)


def cohens_kappa(rater_a: Sequence[T], rater_b: Sequence[T]) -> float:
    """Cohen's kappa for two raters scoring the same N items on a categorical scale.

    Returns a value in [-1, 1]:
    *  1.0  = perfect agreement
    *  0.0  = agreement at chance
    * <0.0  = worse than chance

    Raises:
        ValueError: if inputs differ in length or are empty.
    """
    if len(rater_a) != len(rater_b):
        raise ValueError(
            f"raters must agree in length: got {len(rater_a)} vs {len(rater_b)}",
        )
    if not rater_a:
        raise ValueError("cannot compute kappa on empty inputs")

    n = len(rater_a)
    observed_agree = sum(1 for a, b in zip(rater_a, rater_b, strict=True) if a == b) / n

    a_counts = Counter(rater_a)
    b_counts = Counter(rater_b)
    categories = set(a_counts) | set(b_counts)
    expected_agree = sum((a_counts[c] / n) * (b_counts[c] / n) for c in categories)

    if expected_agree >= 1.0:
        # Both raters used a single category, perfect by construction.
        return 1.0
    return (observed_agree - expected_agree) / (1.0 - expected_agree)


def fleiss_kappa(ratings: Sequence[Sequence[T]]) -> float:
    """Fleiss' kappa: inter-rater agreement for >2 raters.

    Args:
        ratings: A list of rating-lists. ``ratings[i][r]`` is rater ``r``'s
            label for item ``i``. Every item must have the same number of
            raters.

    Returns:
        Kappa in [-1, 1].
    """
    if not ratings:
        raise ValueError("ratings is empty")
    n_raters = len(ratings[0])
    if n_raters < 2:
        raise ValueError("Fleiss' kappa requires ≥2 raters per item")
    if any(len(r) != n_raters for r in ratings):
        raise ValueError("all items must have the same number of raters")

    n_items = len(ratings)
    categories = sorted({label for row in ratings for label in row}, key=str)
    cat_index = {c: i for i, c in enumerate(categories)}

    counts = np.zeros((n_items, len(categories)), dtype=np.int64)
    for i, row in enumerate(ratings):
        for label in row:
            counts[i, cat_index[label]] += 1

    p_j = counts.sum(axis=0) / (n_items * n_raters)
    p_e: float = float((p_j**2).sum())

    p_i = ((counts**2).sum(axis=1) - n_raters) / (n_raters * (n_raters - 1))
    p_bar: float = float(p_i.mean())

    if p_e >= 1.0:
        return 1.0
    return (p_bar - p_e) / (1.0 - p_e)


def _to_float_key(v: object) -> float:
    """Sort key: convert numeric-looking labels to float; raise otherwise.

    Used by ``krippendorff_alpha`` to order labels numerically for ordinal
    and interval metrics. The previous ``key=str`` put '10' between '1'
    and '2' and silently corrupted ordinal distances on any rubric whose
    labels included multi-digit integers.
    """
    return float(v)  # type: ignore[arg-type]


def krippendorff_alpha(
    ratings: Sequence[Sequence[T | None]],
    *,
    metric: str = "nominal",
) -> float:
    """Krippendorff's alpha, handles missing values, multiple raters, multiple metrics.

    Args:
        ratings: ``ratings[i][r]`` is rater ``r``'s label for item ``i``,
            or ``None`` if missing.
        metric: ``"nominal"`` (default), ``"interval"``, or ``"ordinal"``.

    Returns:
        Alpha in (-∞, 1]. ≥0.8 is conventionally considered reliable.

    Notes:
        Implementation follows the coincidence-matrix definition; see
        Krippendorff (2004) §11. We avoid the deps on the
        ``krippendorff`` package because it adds ~3MB and we only need the
        nominal and interval cases.
    """
    if metric not in {"nominal", "interval", "ordinal"}:
        raise ValueError(f"unsupported metric: {metric!r}")

    n_items = len(ratings)
    if n_items == 0:
        raise ValueError("ratings is empty")

    # Flatten to (item_index, value) pairs.
    valid: list[list[T]] = [[v for v in row if v is not None] for row in ratings]
    units = [u for u in valid if len(u) >= 2]
    if not units:
        raise ValueError("alpha requires at least one item with ≥2 ratings")

    distinct = {v for u in units for v in u}
    # For interval/ordinal we need labels ordered numerically; for nominal the
    # order doesn't matter as long as it's stable. Sorting strings of "10",
    # "2", "5" lexicographically would put 10 between 1 and 2 and silently
    # corrupt ordinal/interval distances, fall back to str() only when the
    # labels truly are non-numeric (and the metric is nominal).
    try:
        values = sorted(distinct, key=_to_float_key)
    except (TypeError, ValueError):
        if metric != "nominal":
            raise ValueError("interval/ordinal metric requires numeric labels") from None
        values = sorted(distinct, key=str)
    val_index = {v: i for i, v in enumerate(values)}
    k = len(values)

    coincidence = np.zeros((k, k), dtype=np.float64)
    for u in units:
        m = len(u)
        for p_idx, p in enumerate(u):
            for q_idx, q in enumerate(u):
                if p_idx == q_idx:
                    continue
                coincidence[val_index[p], val_index[q]] += 1.0 / (m - 1)

    n = coincidence.sum()
    if n == 0:
        return 1.0

    n_v = coincidence.sum(axis=1)

    def delta(i: int, j: int) -> float:
        if metric == "nominal":
            return 0.0 if i == j else 1.0
        # ``values`` are sorted strings, to use interval/ordinal we need numerics.
        try:
            a, b = float(values[i]), float(values[j])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "interval/ordinal metric requires numeric labels",
            ) from exc
        if metric == "interval":
            return float((a - b) ** 2)
        # ordinal
        lo, hi = sorted((i, j))
        between = float(n_v[lo:hi].sum() + n_v[hi] / 2 - n_v[lo] / 2)
        return between**2

    d_obs = float(
        sum(coincidence[i, j] * delta(i, j) for i in range(k) for j in range(k)),
    )
    d_exp = float(
        sum(n_v[i] * n_v[j] * delta(i, j) / (n - 1) for i in range(k) for j in range(k)),
    )
    if d_exp == 0:
        return 1.0
    return 1.0 - d_obs / d_exp


def confusion_matrix(rater_a: Sequence[T], rater_b: Sequence[T]) -> dict[tuple[T, T], int]:
    """Pair-count confusion matrix, useful for diagnosing where raters disagree."""
    if len(rater_a) != len(rater_b):
        raise ValueError("rater lengths differ")
    out: dict[tuple[T, T], int] = {}
    for a, b in zip(rater_a, rater_b, strict=True):
        out[(a, b)] = out.get((a, b), 0) + 1
    return out


def prevalence_index(rater_a: Sequence[T], rater_b: Sequence[T]) -> float:
    """Prevalence index P_I (Feinstein & Cicchetti, 1990).

    For binary classifications, ``P_I = |p_yes − p_no|`` where the proportions
    are pooled across both raters. For >2 categories we generalise to the
    spread between the most-used and least-used category. ``P_I`` near 1.0
    means one category dominates, this drives the *kappa paradox* where κ
    is artificially low even at very high observed agreement.

    A value below ~0.5 means kappa is interpretable; above ~0.8 you should
    quote raw agreement (or Gwet's AC₁) alongside κ.
    """
    if len(rater_a) != len(rater_b):
        raise ValueError("rater lengths differ")
    if not rater_a:
        raise ValueError("empty input")

    n = 2 * len(rater_a)
    counts: dict[Any, int] = {}
    for v in (*rater_a, *rater_b):
        counts[v] = counts.get(v, 0) + 1
    if len(counts) < 2:
        return 1.0
    proportions = sorted(c / n for c in counts.values())
    return proportions[-1] - proportions[0]


def bias_index(rater_a: Sequence[T], rater_b: Sequence[T]) -> float:
    """Bias index B_I (Feinstein & Cicchetti, 1990).

    Maximum absolute difference between the two raters' marginal
    distributions. ``B_I`` near 0 means raters use the categories with
    similar frequencies; large ``B_I`` indicates that one rater is
    systematically more permissive than the other.
    """
    if len(rater_a) != len(rater_b):
        raise ValueError("rater lengths differ")
    if not rater_a:
        raise ValueError("empty input")
    n = len(rater_a)
    a_counts: dict[Any, int] = {}
    b_counts: dict[Any, int] = {}
    for v in rater_a:
        a_counts[v] = a_counts.get(v, 0) + 1
    for v in rater_b:
        b_counts[v] = b_counts.get(v, 0) + 1
    categories = set(a_counts) | set(b_counts)
    return max(abs(a_counts.get(c, 0) / n - b_counts.get(c, 0) / n) for c in categories)


def gwet_ac1(rater_a: Sequence[T], rater_b: Sequence[T]) -> float:
    """Gwet's AC₁, paradox-resistant alternative to Cohen's κ.

    Gwet's AC₁ replaces κ's chance-agreement term with a value that is
    invariant to marginal skew, so it does not collapse to ~0 at very high
    agreement on imbalanced data (the "kappa paradox"; see Gwet 2008,
    *Br J Math Stat Psychol* 61:29–48). When observed agreement is high
    and ``prevalence_index`` is close to 1.0, prefer this statistic.
    """
    if len(rater_a) != len(rater_b):
        raise ValueError("rater lengths differ")
    if not rater_a:
        raise ValueError("empty input")
    n = len(rater_a)
    p_obs = sum(1 for a, b in zip(rater_a, rater_b, strict=True) if a == b) / n
    a_counts: dict[Any, int] = {}
    b_counts: dict[Any, int] = {}
    for v in rater_a:
        a_counts[v] = a_counts.get(v, 0) + 1
    for v in rater_b:
        b_counts[v] = b_counts.get(v, 0) + 1
    categories = set(a_counts) | set(b_counts)
    q = len(categories)
    if q < 2:
        return 1.0
    pi_sum = sum(((a_counts.get(c, 0) + b_counts.get(c, 0)) / (2 * n)) ** 2 for c in categories)
    p_e = (1 - pi_sum) / (q - 1)
    if p_e >= 1.0:
        return 1.0
    return (p_obs - p_e) / (1 - p_e)
