"""LLM-judge bias audits.

Two audits run by default, only the ones that apply to point-wise scoring
judges, since that's what :class:`evalkit.judges.CalibratedJudge` is:

1. **Length bias**, scoring an answer twice (short vs, padded with neutral
   whitespace), does the score change purely with length? This is universal:
   any rubric that asks the judge for a quality score is susceptible.

2. **Position bias**. *only* meaningful for pairwise rubrics whose
   criteria are literally ``A`` and ``B`` (i.e., "rate slot A's quality" and
   "rate slot B's quality"). For these, we present the same content in both
   slots and check that neither slot is systematically preferred. For
   non-pairwise rubrics this audit is N/A and the report channel is ``None``.

3. **Self-preference bias**. *not* run by default. Detecting self-preference
   requires sampling outputs from multiple model families and feeding labelled
   pairs to the judge. A library can't synthesize this; users who care must
   supply real same-family / cross-family pairs to
   :func:`audit_self_preference`. Including it in default ``audit_biases``
   would silently report meaningless zeros (which the previous version did).

This module is the single piece of evaluation methodology most homemade eval
tools get wrong. We optimise for *not lying about what we measured*.

References:
    * Wang et al. (2023). Large Language Models are not Fair Evaluators.
    * Zheng et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.
    * Saito et al. (2023). Verbosity Bias in Preference Labeling by Large
      Language Models.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from evalkit.exceptions import BiasDetected, JudgeError

if TYPE_CHECKING:  # pragma: no cover
    from evalkit.judges.base import Judge


@dataclass(frozen=True, slots=True)
class BiasReport:
    """Summary of bias audits.

    A channel may be ``None`` when the audit is N/A for the judge's rubric
    (e.g., ``position_bias`` is ``None`` for non-pairwise rubrics; we don't
    fabricate a number).
    """

    length_bias: float | None
    position_bias: float | None
    self_pref_bias: float | None
    threshold: float

    @property
    def channels(self) -> dict[str, float]:
        """Return only the channels that were actually measured (non-None)."""
        out: dict[str, float] = {}
        if self.length_bias is not None:
            out["length"] = self.length_bias
        if self.position_bias is not None:
            out["position"] = self.position_bias
        if self.self_pref_bias is not None:
            out["self_pref"] = self.self_pref_bias
        return out

    @property
    def worst(self) -> tuple[str, float] | None:
        ch = self.channels
        if not ch:
            return None
        return max(ch.items(), key=lambda kv: abs(kv[1]))

    def passes(self) -> bool:
        worst = self.worst
        if worst is None:
            # No channel measured, vacuously passes; calibration loop logs this.
            return True
        return abs(worst[1]) <= self.threshold

    def raise_if_failing(self) -> None:
        worst = self.worst
        if worst is None:
            return
        kind, mag = worst
        if abs(mag) > self.threshold:
            raise BiasDetected(kind=kind, magnitude=mag, threshold=self.threshold)


# ---- Length bias (point-wise; universal) ---------------------------------


def audit_length_bias(
    judge: Judge,
    short_long_pairs: Sequence[tuple[str, str]] | None = None,
    *,
    n_pairs: int = 8,
) -> float:
    """Mean ``score(long) − score(short)`` for length-equivalent answers.

    Returns the mean delta in [0, 1] units. A judge that ignores length will
    return ~0; a length-biased judge returns positive.

    The default ``short_long_pairs`` are constructed by padding a short
    answer with content-neutral whitespace. If you need rubric-specific
    pairs, pass your own.
    """
    pairs = list(short_long_pairs) if short_long_pairs is not None else _synth_short_long(n_pairs)
    if not pairs:
        return 0.0
    deltas: list[float] = []
    for short, long in pairs:
        s_short = judge.score(input_data={"q": "evaluate"}, output_data={"answer": short})
        s_long = judge.score(input_data={"q": "evaluate"}, output_data={"answer": long})
        deltas.append(s_long.score - s_short.score)
    return sum(deltas) / len(deltas)


# ---- Position bias (pairwise rubrics only) -------------------------------


def is_pairwise_rubric(judge: Judge) -> bool:
    """Heuristic: a rubric is "pairwise" iff it has both ``A`` and ``B`` criteria.

    Pairwise rubrics ask the judge to score *two outputs at once* in slots A
    and B. that's the structural form that allows position-bias detection.
    """
    rubric = getattr(judge, "rubric", None)
    if rubric is None:
        return False
    names = set(getattr(rubric, "criterion_names", []) or [])
    return "A" in names and "B" in names


def audit_position_bias(
    judge: Judge,
    pair_contents: Sequence[Mapping[str, Any]] | None = None,
    *,
    n_pairs: int = 8,
) -> float:
    """Slot-A preference on identical-content pairs, in [-1, 1].

    Methodology: present the same content X in both slots A and B
    (``output_data={"A": X, "B": X}``). A position-unbiased judge gives
    equal scores to A and B. The returned value is the mean of
    ``score_A − score_B`` across pairs, positive means slot-A bias,
    negative means slot-B bias, zero means none.

    Requires the judge's rubric to have both ``A`` and ``B`` criteria
    (i.e., a *pairwise* rubric, see :func:`is_pairwise_rubric`). Use of a
    non-pairwise rubric raises :class:`JudgeError` rather than silently
    returning 0.
    """
    if not is_pairwise_rubric(judge):
        raise JudgeError(
            "audit_position_bias requires a pairwise rubric (criteria 'A' and 'B'). "
            "Use audit_length_bias for point-wise judges, or build a pairwise rubric.",
        )
    contents = list(pair_contents) if pair_contents is not None else _synth_contents(n_pairs)
    if not contents:
        return 0.0
    deltas: list[float] = []
    for content in contents:
        verdict = judge.score(
            input_data={"task": "compare"},
            output_data={"A": content, "B": content},
        )
        a = float(verdict.criterion_scores.get("A", 0))
        b = float(verdict.criterion_scores.get("B", 0))
        deltas.append((a - b) / max(1.0, max(abs(a), abs(b))))
    return sum(deltas) / len(deltas)


# ---- Self-preference (user-supplied data only) ---------------------------


def audit_self_preference(
    judge: Judge,
    same_family_pairs: Sequence[tuple[Any, Any]],
    cross_family_pairs: Sequence[tuple[Any, Any]],
) -> float:
    """Self-preference bias: ``win_rate(same) − win_rate(cross)``.

    The caller MUST supply real outputs labelled by model family. Pass
    ``same_family_pairs`` as ``(judge_family_output, judge_family_output)``
    duos and ``cross_family_pairs`` as
    ``(judge_family_output, other_family_output)`` duos. Both must use a
    pairwise rubric.

    Returns 0.0 when either list is empty (no measurement).
    """
    if not is_pairwise_rubric(judge):
        raise JudgeError(
            "audit_self_preference requires a pairwise rubric (criteria 'A' and 'B').",
        )
    if not same_family_pairs or not cross_family_pairs:
        return 0.0

    def _slot_a_wins(pair: tuple[Any, Any]) -> int:
        verdict = judge.score(
            input_data={"task": "compare"},
            output_data={"A": pair[0], "B": pair[1]},
        )
        a = float(verdict.criterion_scores.get("A", 0))
        b = float(verdict.criterion_scores.get("B", 0))
        return 1 if a > b else 0

    same_wr = sum(_slot_a_wins(p) for p in same_family_pairs) / len(same_family_pairs)
    cross_wr = sum(_slot_a_wins(p) for p in cross_family_pairs) / len(cross_family_pairs)
    return same_wr - cross_wr


# ---- Driver --------------------------------------------------------------


def audit_biases(
    judge: Judge,
    *,
    threshold: float = 0.15,
    n_pairs: int = 8,
) -> BiasReport:
    """Run the bias audits applicable to ``judge`` and return a single report.

    For point-wise rubrics (the common case): length bias only.
    For pairwise rubrics (criteria ``A`` + ``B``): length + position.
    Self-preference is never run automatically, pass real data to
    :func:`audit_self_preference` directly.

    Args:
        judge: anything implementing :class:`evalkit.judges.base.Judge`.
        threshold: max absolute bias before :meth:`BiasReport.raise_if_failing`
            raises :class:`evalkit.exceptions.BiasDetected`.
        n_pairs: number of synthetic pairs per audit.
    """
    length = audit_length_bias(judge, n_pairs=n_pairs)
    position: float | None = None
    if is_pairwise_rubric(judge):
        position = audit_position_bias(judge, n_pairs=n_pairs)
    return BiasReport(
        length_bias=length,
        position_bias=position,
        self_pref_bias=None,  # never auto-run; user-supplied only
        threshold=threshold,
    )


# ---- helpers -------------------------------------------------------------


def _synth_short_long(n: int) -> list[tuple[str, str]]:
    """Length-equivalent pairs: short answer + the same answer padded with whitespace.

    Whitespace is content-neutral, a faithfulness/honesty/etc, rubric has
    nothing to react to except length itself.
    """
    return [(f"Answer {i}.", f"Answer {i}." + (" " * 200)) for i in range(n)]


def _synth_contents(n: int) -> list[dict[str, Any]]:
    """Identical-content "outputs" for position-bias detection.

    The same dict is presented in both slots A and B by ``audit_position_bias``;
    any preference for one slot over the other is purely positional.
    """
    return [{"answer": f"answer-{i}"} for i in range(n)]
