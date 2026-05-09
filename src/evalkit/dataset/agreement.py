"""Inter-rater agreement diagnostics for golden datasets.

When a dataset has multiple ``labels[]`` per row, this module computes
Cohen's κ (or Fleiss' for >2 raters) plus Krippendorff's α (which handles
missing values robustly) plus the κ-paradox indices and Gwet's AC₁ on the
two-rater case. The combination tells you both *what* the agreement number
is and *whether you can trust it*.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from evalkit.config import DatasetRow
from evalkit.dataset.store import GoldenDataset
from evalkit.judges.stats import (
    bias_index,
    cohens_kappa,
    fleiss_kappa,
    gwet_ac1,
    krippendorff_alpha,
    prevalence_index,
)


@dataclass(frozen=True, slots=True)
class AgreementReport:
    """Summary of inter-rater agreement on a labelled dataset.

    Attributes:
        n_rated_rows: rows with ≥2 raters.
        n_raters: rater count used for the κ computation (truncated to the
            minimum across rows when heterogeneous).
        kappa: Cohen's κ (n_raters == 2) or Fleiss' κ (n_raters > 2).
        statistic: ``"cohen"`` or ``"fleiss"``.
        krippendorff_alpha: ordinal Krippendorff's α, robust to missing
            values and rater-count heterogeneity. ``NaN`` if all label
            values are non-numeric.
        prevalence_index: pooled |P_max − P_min|; high values flag the κ
            paradox (consult ``gwet_ac1``).
        bias_index: max marginal-distribution gap between raters (only
            populated for the two-rater case).
        gwet_ac1: paradox-resistant alternative to κ (two-rater only).
        low_agreement_ids: rows whose raters disagreed by more than
            ``low_threshold`` raw points.
    """

    n_rated_rows: int
    n_raters: int
    kappa: float
    statistic: str
    krippendorff_alpha: float
    prevalence_index: float
    bias_index: float
    gwet_ac1: float
    low_agreement_ids: list[str]


def compute_agreement(
    dataset: GoldenDataset | Iterable[dict[str, object]],
    *,
    low_threshold: float = 0.5,
) -> AgreementReport:
    """Score a dataset's inter-rater agreement.

    Each row is expected to have ``labels`` with at least two ``{"rater": ..., "score": ...}``
    entries. Rows with fewer than two raters are excluded from κ but still
    contribute to Krippendorff's α (which handles missing labels). Rows
    whose raters disagree by more than ``low_threshold`` raw points are
    listed in ``low_agreement_ids`` for triage.

    Args:
        dataset: a :class:`GoldenDataset` or an iterable of row dicts.
        low_threshold: per-row disagreement threshold (raw point delta).
    """
    rated_rows: list[list[int]] = []
    rated_ids: list[str] = []
    low_ids: list[str] = []
    # Krippendorff handles missing entries, keep the full per-row labels even
    # when rater counts vary, padded with None to the row's natural width.
    krippendorff_input: list[list[int | None]] = []

    rows = list(dataset)

    for row in rows:
        if isinstance(row, DatasetRow):
            row_id = row.id
            labels_raw = list(row.labels)
        elif isinstance(row, dict):
            row_id = str(row.get("id"))
            labels_raw = list(row.get("labels") or [])
        else:
            continue
        scores = []
        for lab in labels_raw:
            s = lab.get("score") if isinstance(lab, dict) else getattr(lab, "score", None)
            if isinstance(s, int | float):
                scores.append(int(s))
        if not scores:
            continue
        krippendorff_input.append([*scores])
        if len(scores) < 2:
            continue
        rated_rows.append(scores)
        rated_ids.append(row_id)
        if max(scores) - min(scores) > low_threshold:
            low_ids.append(row_id)

    if not rated_rows:
        return AgreementReport(
            n_rated_rows=0,
            n_raters=0,
            kappa=float("nan"),
            statistic="cohen",
            krippendorff_alpha=float("nan"),
            prevalence_index=float("nan"),
            bias_index=float("nan"),
            gwet_ac1=float("nan"),
            low_agreement_ids=[],
        )

    n_raters = len(rated_rows[0])
    if any(len(r) != n_raters for r in rated_rows):
        # κ-style stats need uniform rater counts, truncate. Krippendorff α
        # is computed on the *un*truncated input so it sees all the data.
        n_raters = min(len(r) for r in rated_rows)
        rated_rows = [r[:n_raters] for r in rated_rows]

    if n_raters == 2:
        rater_a = [r[0] for r in rated_rows]
        rater_b = [r[1] for r in rated_rows]
        kappa = cohens_kappa(rater_a, rater_b)
        statistic = "cohen"
        prev = prevalence_index(rater_a, rater_b)
        bidx = bias_index(rater_a, rater_b)
        ac1 = gwet_ac1(rater_a, rater_b)
    else:
        kappa = fleiss_kappa(rated_rows)
        statistic = "fleiss"
        # Pool all ratings for the prevalence diagnostic. Bias index / AC₁
        # are pairwise stats we don't generalise here, keep them NaN to
        # signal "not applicable for n_raters > 2".
        flat = [v for row in rated_rows for v in row]
        prev = prevalence_index(flat, flat)  # pooled distribution
        bidx = float("nan")
        ac1 = float("nan")

    # Krippendorff's α, pad to a uniform width with None so missing labels
    # are explicit. Use ordinal metric since label scores are ordered.
    width = max(len(r) for r in krippendorff_input)
    padded: list[list[int | None]] = [[*r] + [None] * (width - len(r)) for r in krippendorff_input]
    try:
        alpha = krippendorff_alpha(padded, metric="ordinal")
    except ValueError:
        alpha = float("nan")

    return AgreementReport(
        n_rated_rows=len(rated_rows),
        n_raters=n_raters,
        kappa=kappa,
        statistic=statistic,
        krippendorff_alpha=alpha,
        prevalence_index=prev,
        bias_index=bidx,
        gwet_ac1=ac1,
        low_agreement_ids=low_ids,
    )
