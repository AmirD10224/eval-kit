"""The flagship judge: rubric-driven, calibrated against human labels, bias-audited.

Workflow::

    judge = CalibratedJudge.from_rubric("rubrics/faithfulness.yaml")
    report = judge.calibrate(
        "golden.jsonl",
        predictions="calibration-predictions.jsonl",  # candidate outputs from your system
    )
    if not report.passes:
        raise SystemExit(report.failure_reason)
    judge.score(input_data=..., output_data=...)

The "calibrated" part is the differentiator vs, naive ``judge_score = llm.eval()``
setups: we measure agreement with human labels (Cohen's kappa), audit for the
biases that apply to the rubric form, surface the κ paradox indices so a
high-skew dataset doesn't silently sink κ, and refuse to deploy when
agreement is too low.
"""

from __future__ import annotations

import json
import statistics
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evalkit.exceptions import CalibrationFailure, DatasetError, JudgeError
from evalkit.judges.base import JudgeOutput
from evalkit.judges.bias import BiasReport, audit_biases
from evalkit.judges.rubric import Rubric
from evalkit.judges.stats import (
    bias_index,
    cohens_kappa,
    fleiss_kappa,
    gwet_ac1,
    prevalence_index,
)
from evalkit.llm.client import DEFAULT_JUDGE_MODEL, LLMClient

# ---------- Calibration report ---------------------------------------------


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    """Output of :meth:`CalibratedJudge.calibrate`.

    Carries Cohen's κ alongside the κ-paradox diagnostics so callers can
    decide whether κ is interpretable on their data.

    Attributes:
        rubric: name of the rubric.
        n_samples: number of golden rows that contributed to κ.
        scale: integer scale used to bin judge & human scores for κ
            (derived from the rubric or the labels, see calibrate's
            implementation).
        cohen_kappa: Cohen's κ between mode-of-human labels and the binned
            judge score.
        fleiss_kappa: Fleiss' κ across humans (only when raters per row are
            uniform and ≥2).
        prevalence_index: |P_max − P_min| over pooled label proportions.
            Above ~0.8, κ is in the paradox regime, prefer ``gwet_ac1``.
        bias_index: max marginal-distribution gap between human-mode and
            judge labels. Large values mean systematic over/under-rating.
        gwet_ac1: paradox-resistant complement to κ.
        bias: bias-audit channels (length always present; position only for
            pairwise rubrics).
        floor: κ floor below which calibration fails.
        failure_reason: ``None`` ⇒ passes.
    """

    rubric: str
    n_samples: int
    scale: int
    cohen_kappa: float
    fleiss_kappa: float | None
    prevalence_index: float
    bias_index: float
    gwet_ac1: float
    bias: BiasReport | None
    floor: float
    failure_reason: str | None = None

    @property
    def passes(self) -> bool:
        return self.failure_reason is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rubric": self.rubric,
            "n_samples": self.n_samples,
            "scale": self.scale,
            "cohen_kappa": self.cohen_kappa,
            "fleiss_kappa": self.fleiss_kappa,
            "prevalence_index": self.prevalence_index,
            "bias_index": self.bias_index,
            "gwet_ac1": self.gwet_ac1,
            "bias": (
                None
                if self.bias is None
                else {
                    "length": self.bias.length_bias,
                    "position": self.bias.position_bias,
                    "self_pref": self.bias.self_pref_bias,
                    "threshold": self.bias.threshold,
                }
            ),
            "floor": self.floor,
            "failure_reason": self.failure_reason,
            "passes": self.passes,
        }


# ---------- The judge -------------------------------------------------------


@dataclass
class CalibratedJudge:
    """Rubric-backed LLM judge with calibration and bias auditing.

    Construct via the :meth:`from_rubric` / :meth:`from_rubric_text`
    classmethods rather than ``__init__`` directly.
    """

    rubric: Rubric
    client: LLMClient
    model: str = DEFAULT_JUDGE_MODEL
    calibrated: bool = field(default=False, init=False)
    calibration_report: CalibrationReport | None = field(default=None, init=False)

    # ---------- construction --------------------------------------------

    @classmethod
    def from_rubric(
        cls,
        rubric_path: str | Path,
        *,
        client: LLMClient | None = None,
        model: str = DEFAULT_JUDGE_MODEL,
    ) -> CalibratedJudge:
        rubric = Rubric.from_yaml(rubric_path)
        return cls(rubric=rubric, client=_resolve_client(client), model=model)

    @classmethod
    def from_rubric_text(
        cls,
        text: str,
        *,
        client: LLMClient | None = None,
        model: str = DEFAULT_JUDGE_MODEL,
    ) -> CalibratedJudge:
        rubric = Rubric.from_text(text)
        return cls(rubric=rubric, client=_resolve_client(client), model=model)

    # ---------- scoring -------------------------------------------------

    def score(
        self,
        *,
        input_data: Mapping[str, Any],
        output_data: Mapping[str, Any],
        expected: Mapping[str, Any] | None = None,
    ) -> JudgeOutput:
        system = self.rubric.render_system()
        prompt = self.rubric.render_user(
            input_data=input_data,
            output_data=output_data,
            expected=expected,
        )
        response = self.client.complete(
            system=system,
            prompt=prompt,
            model=self.model,
            max_tokens=512,
            temperature=0.0,
        )
        return self._parse(response.text)

    # ---------- calibration --------------------------------------------

    def calibrate(
        self,
        golden_path: str | Path,
        *,
        predictions: str | Path | Mapping[str, Mapping[str, Any]] | None = None,
        run_bias_audit: bool = True,
        raise_on_fail: bool = False,
    ) -> CalibrationReport:
        """Score every golden row, compare against humans, compute κ + paradox indices.

        Args:
            golden_path: JSONL path to a golden dataset. Each row must carry
                a ``labels`` list with one or more ``{"rater": ..., "score": int}``
                entries.
            predictions: candidate outputs to score. Three accepted forms:
                a path to a predictions JSONL (id → output), a mapping
                ``{row_id: output_dict}``, or ``None`` (legacy fallback -
                scores ``row.expected`` and emits a deprecation warning).
                The legacy fallback corresponds to the old behaviour where
                calibration scored the gold answer; that conflates judge
                quality with golden-distribution agreement and is no longer
                recommended.
            run_bias_audit: also run the applicable bias audits.
            raise_on_fail: raise :class:`CalibrationFailure` on failure.

        Returns:
            A :class:`CalibrationReport` carrying κ, Fleiss' κ (if applicable),
            prevalence + bias indices, Gwet's AC₁, and the bias audit.
        """
        from evalkit.dataset.store import GoldenDataset  # noqa: PLC0415

        dataset = GoldenDataset.load(golden_path)
        rows = list(dataset)
        floor = self.rubric.config.calibration.kappa_floor
        cal_cfg = self.rubric.config.calibration
        # Use the largest criterion scale in the rubric, that's the scale on
        # which the rubric author elicited human labels.
        scale = max(c.scale for c in self.rubric.config.criteria)

        if len(rows) < cal_cfg.min_samples:
            return self._fail(
                rubric_name=self.rubric.name,
                n_samples=len(rows),
                scale=scale,
                floor=floor,
                reason=f"need ≥{cal_cfg.min_samples} labelled rows, got {len(rows)}",
                raise_on_fail=raise_on_fail,
            )

        preds_map = _resolve_predictions(predictions, dataset)

        judge_labels: list[int] = []
        human_labels: list[int] = []
        all_human: list[list[int]] = []

        for row in rows:
            human = _coerce_human_score(row.labels, scale=scale)
            if human is None:
                continue
            output_data = preds_map.get(row.id) if preds_map is not None else row.expected
            if output_data is None:
                continue
            verdict = self.score(
                input_data=row.input,
                output_data=output_data,
                expected=row.expected,
            )
            judge_score = _bin_aggregate(verdict.score, scale=scale)
            human_labels.append(human["median"])
            judge_labels.append(judge_score)
            all_human.append(human["all"])

        if len(human_labels) < cal_cfg.min_samples:
            return self._fail(
                rubric_name=self.rubric.name,
                n_samples=len(human_labels),
                scale=scale,
                floor=floor,
                reason=(
                    "not enough rows with usable human labels: "
                    f"{len(human_labels)} < {cal_cfg.min_samples}"
                ),
                raise_on_fail=raise_on_fail,
            )

        kappa = cohens_kappa(human_labels, judge_labels)
        prev_idx = prevalence_index(human_labels, judge_labels)
        b_idx = bias_index(human_labels, judge_labels)
        ac1 = gwet_ac1(human_labels, judge_labels)

        fleiss: float | None = None
        if all_human:
            n_first = len(all_human[0])
            if n_first >= 2 and all(len(r) == n_first for r in all_human):
                try:
                    fleiss = fleiss_kappa(all_human)
                except ValueError:
                    fleiss = None

        bias = (
            audit_biases(self, threshold=cal_cfg.bias_threshold, n_pairs=8)
            if run_bias_audit
            else None
        )

        failure: str | None = None
        if kappa < floor:
            # If the κ paradox is plausibly the cause, surface that explicitly
            # rather than just blaming the judge.
            if prev_idx > 0.8 and ac1 >= floor:
                failure = (
                    f"cohen_kappa={kappa:.3f} < floor={floor:.3f}, but prevalence_index="
                    f"{prev_idx:.3f} suggests κ paradox; gwet_ac1={ac1:.3f} ≥ floor. "
                    "consider quoting AC₁ instead of κ on this dataset."
                )
            else:
                failure = f"cohen_kappa={kappa:.3f} < floor={floor:.3f}"
        elif bias is not None and not bias.passes():
            worst = bias.worst
            if worst is not None:
                kind, mag = worst
                failure = (
                    f"bias audit failed: {kind} bias = {mag:+.3f} (threshold={bias.threshold:.3f})"
                )

        report = CalibrationReport(
            rubric=self.rubric.name,
            n_samples=len(human_labels),
            scale=scale,
            cohen_kappa=kappa,
            fleiss_kappa=fleiss,
            prevalence_index=prev_idx,
            bias_index=b_idx,
            gwet_ac1=ac1,
            bias=bias,
            floor=floor,
            failure_reason=failure,
        )
        self.calibration_report = report
        self.calibrated = report.passes
        if raise_on_fail and not report.passes:
            raise CalibrationFailure(kappa, floor, detail=failure or "")
        return report

    # ---------- internals ----------------------------------------------

    def _fail(
        self,
        *,
        rubric_name: str,
        n_samples: int,
        scale: int,
        floor: float,
        reason: str,
        raise_on_fail: bool,
    ) -> CalibrationReport:
        report = CalibrationReport(
            rubric=rubric_name,
            n_samples=n_samples,
            scale=scale,
            cohen_kappa=float("nan"),
            fleiss_kappa=None,
            prevalence_index=float("nan"),
            bias_index=float("nan"),
            gwet_ac1=float("nan"),
            bias=None,
            floor=floor,
            failure_reason=reason,
        )
        self.calibration_report = report
        if raise_on_fail:
            raise CalibrationFailure(0.0, floor, detail=reason)
        return report

    def _parse(self, text: str) -> JudgeOutput:
        try:
            data = json.loads(_strip_fences(text))
        except json.JSONDecodeError as exc:
            raise JudgeError(f"could not parse judge response as JSON: {text!r}") from exc

        if not isinstance(data, dict):
            raise JudgeError(f"judge response must be a JSON object, got {type(data).__name__}")

        criterion_scores: dict[str, int] = {}
        if "score" in data and isinstance(data["score"], int | float):
            for c in self.rubric.config.criteria:
                criterion_scores[c.name] = int(data["score"])
        else:
            for c in self.rubric.config.criteria:
                v = data.get(c.name)
                if not isinstance(v, int | float):
                    raise JudgeError(
                        f"missing or non-numeric score for criterion {c.name!r}: {v!r}",
                    )
                criterion_scores[c.name] = int(v)

        score = self.rubric.aggregate(
            {k: float(v) for k, v in criterion_scores.items()},
        )
        reasoning = str(data.get("reasoning", ""))
        return JudgeOutput(
            score=score,
            criterion_scores=criterion_scores,
            reasoning=reasoning,
            raw_response=text,
        )


# ---------- module-private helpers ----------------------------------------


def _resolve_client(client: LLMClient | None) -> LLMClient:
    if client is not None:
        return client
    from evalkit.llm.client import AnthropicClient  # noqa: PLC0415

    return AnthropicClient()


def _resolve_predictions(
    predictions: str | Path | Mapping[str, Mapping[str, Any]] | None,
    dataset: Any,  # GoldenDataset, but circular import. Any keeps mypy happy
) -> dict[str, Mapping[str, Any]] | None:
    """Normalise the ``predictions`` argument into ``{row_id: output_dict}`` (or None).

    Returns ``None`` when the caller passed ``None`` and the loop should fall
    back to ``row.expected`` (with a deprecation warning).
    """
    if predictions is None:
        warnings.warn(
            "calibrate(predictions=None) scores the gold answer as the candidate output; "
            "this conflates judge quality with golden-distribution agreement. Pass a "
            "predictions JSONL or {row_id: output} mapping for methodologically sound "
            "calibration. See docs/concepts/calibration.md.",
            DeprecationWarning,
            stacklevel=3,
        )
        return None

    if isinstance(predictions, Mapping):
        return {str(k): dict(v) for k, v in predictions.items()}

    p = Path(predictions)
    if not p.exists():
        raise DatasetError(f"predictions file not found: {p}")
    out: dict[str, Mapping[str, Any]] = {}
    for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetError(f"{p}:{lineno}: invalid JSON: {exc}") from exc
        row_id = obj.get("id")
        output = obj.get("output")
        if not isinstance(row_id, str) or not isinstance(output, Mapping):
            raise DatasetError(
                f"{p}:{lineno}: predictions must be {{'id': str, 'output': mapping}}",
            )
        out[row_id] = output
    missing = [r.id for r in dataset if r.id not in out]
    if missing:
        sample = ", ".join(missing[:5])
        suffix = "" if len(missing) <= 5 else f" (+{len(missing) - 5} more)"
        raise DatasetError(f"predictions missing for golden rows: {sample}{suffix}")
    return out


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1 :]
        if text.endswith("```"):
            text = text[:-3].rstrip()
        if text.startswith("json"):
            text = text[len("json") :].lstrip()
    return text


def _bin_aggregate(score: float, scale: int = 5) -> int:
    """Bin an aggregate score in [0, 1] back to a 1..scale int.

    Boundaries are symmetric: bin ``b`` covers
    ``[(b-1.5)/(scale-1), (b-0.5)/(scale-1))`` for b ∈ [2, scale-1], with bins
    1 and ``scale`` taking the open ends. So 0.5 on a 1..5 scale lands in
    bin 3, not bin 1 (the previous behaviour).
    """
    if score <= 0:
        return 1
    if score >= 1:
        return scale
    if scale <= 1:
        return 1
    width = 1.0 / (scale - 1)
    bin_idx = int((score + width / 2) // width) + 1
    return max(1, min(scale, bin_idx))


def _coerce_human_score(
    labels: Sequence[Mapping[str, Any]],
    *,
    scale: int = 5,
) -> dict[str, Any] | None:
    """Reduce a list of rater dicts to ``{"median": int, "all": [int...]}`` or None.

    For ordinal labels the median is the standard collapse. *not* the mode,
    which (a) treats ordinal data as nominal and (b) tie-breaks arbitrarily.
    Tied medians are resolved with ``statistics.median_low`` for stability,
    then clamped to ``1..scale``.
    """
    scores: list[int] = []
    for label in labels:
        s = label.get("score")
        if not isinstance(s, int | float):
            continue
        scores.append(int(s))
    if not scores:
        return None
    median = int(statistics.median_low(scores))
    median = max(1, min(scale, median))
    return {"median": median, "all": scores}
