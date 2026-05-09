"""Parallel suite runner.

Loads a :class:`SuiteConfig`, the matching golden dataset, the predictions
JSONL, and computes every metric across all samples using a thread pool.
Per-metric work is synchronous (the underlying LLM calls block on HTTP),
which keeps the model simple, true async would buy little here because
the bottleneck is judge latency, not Python.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from evalkit.config import MetricSpec, PredictionRow, SuiteConfig
from evalkit.dataset.store import GoldenDataset
from evalkit.exceptions import ConfigError, EvalKitError
from evalkit.runner.report import MetricResult, Sample, SuiteReport
from evalkit.runner.suite import load_suite_config

if TYPE_CHECKING:  # pragma: no cover
    from evalkit.judges.base import Judge
    from evalkit.llm.client import LLMClient


# A scorer takes (input, output, expected) → score in [0, 1].
ScorerFn = Callable[[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any] | None], float]


# ---------- public Suite ---------------------------------------------------


@dataclass
class Suite:
    """A loaded eval suite ready to run.

    Use :meth:`from_yaml` to load from disk; :meth:`run` to execute.
    """

    config: SuiteConfig
    base_dir: Path
    custom_scorers: dict[str, ScorerFn]

    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
        custom_scorers: Mapping[str, ScorerFn] | None = None,
    ) -> Suite:
        p = Path(path)
        config = load_suite_config(p)
        return cls(
            config=config,
            base_dir=p.parent,
            custom_scorers=dict(custom_scorers or {}),
        )

    def register_scorer(self, name: str, fn: ScorerFn) -> None:
        """Register a custom scorer for ``kind: custom`` metrics."""
        self.custom_scorers[name] = fn

    def run(
        self,
        *,
        predictions: str | Path | None = None,
        client: LLMClient | None = None,
    ) -> SuiteResult:
        """Execute the full suite. Returns a :class:`SuiteResult`."""
        from evalkit.judges.calibrated import CalibratedJudge  # noqa: PLC0415
        from evalkit.judges.rubric import Rubric  # noqa: PLC0415
        from evalkit.llm.client import AnthropicClient  # noqa: PLC0415

        dataset = GoldenDataset.load(self._resolve(self.config.dataset))
        # Predictions resolution rule:
        # * runtime-supplied (from CLI/API): take as-is. The caller already
        #   typed the path; double-resolving against the suite dir
        #   pre-pends `examples/qa-rag/` and crashes the canonical
        #   "evalkit run" example.
        # * declared in suite YAML (`predictions:`): resolve against the
        #   suite dir, same path-traversal rules as `dataset:` and `rubric:`.
        if predictions is not None:
            preds = _load_predictions(Path(predictions))
        elif self.config.predictions:
            preds = _load_predictions(self._resolve(self.config.predictions))
        else:
            preds = _self_pred(dataset)
        _check_alignment(dataset, preds)

        resolved_client = client or AnthropicClient()

        scorers: list[tuple[MetricSpec, _Scorer]] = []
        for spec in self.config.metrics:
            scorer = self._build_scorer(
                spec, client=resolved_client, rubric_loader=Rubric, judge_cls=CalibratedJudge
            )
            scorers.append((spec, scorer))

        started = time.perf_counter()
        timestamp = datetime.now(UTC).isoformat()
        metric_results: list[MetricResult] = []

        for spec, scorer in scorers:
            samples = _run_metric_parallel(
                spec=spec,
                scorer=scorer,
                dataset=dataset,
                preds=preds,
                parallelism=self.config.parallelism,
            )
            mean = sum(s.score for s in samples) / len(samples) if samples else 0.0
            metric_results.append(
                MetricResult(
                    name=spec.name,
                    kind=spec.kind,
                    mean=mean,
                    n=len(samples),
                    samples=samples,
                    higher_is_better=spec.higher_is_better,
                    target=spec.target,
                ),
            )

        duration = time.perf_counter() - started
        report = SuiteReport(
            suite_name=self.config.name,
            metrics=metric_results,
            n_samples=len(dataset),
            judge_model=self.config.judge_model,
            timestamp=timestamp,
            duration_seconds=duration,
            seed=self.config.seed,
            git_sha=_git_sha(self.base_dir),
        )
        return SuiteResult(report=report)

    # ---------- private --------------------------------------------------

    def _resolve(self, rel: str | Path) -> Path:
        """Resolve a path declared *inside* the suite YAML (`dataset:`, `rubric:`, etc.).

        These paths must be **relative to the suite directory** and stay
        within it. We refuse absolute paths and ``..`` components, without
        this, a malicious PR contributor can have the action read arbitrary
        runner-host files (``/home/runner/.docker/config.json`` etc.) whose
        contents end up echoed into the public CI log via pydantic's
        ValidationError messages.
        """
        p = Path(rel)
        if p.is_absolute():
            raise ConfigError(
                f"path inside suite YAML must be relative, got absolute: {rel!r}",
            )
        if any(part == ".." for part in p.parts):
            raise ConfigError(
                f"path inside suite YAML must not contain '..': {rel!r}",
            )
        base = self.base_dir.resolve()
        target = (base / p).resolve()
        # belt-and-braces: ensure the resolved path is still under base.
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ConfigError(
                f"path inside suite YAML escapes the suite directory: {rel!r}",
            ) from exc
        return target

    def _build_scorer(
        self,
        spec: MetricSpec,
        *,
        client: LLMClient,
        rubric_loader: Any,
        judge_cls: Any,
    ) -> _Scorer:
        if spec.kind == "judge":
            if not spec.rubric:
                raise ConfigError(f"metric {spec.name!r}: kind=judge requires rubric path")
            rubric = rubric_loader.from_yaml(self._resolve(spec.rubric))
            judge: Judge = judge_cls(rubric=rubric, client=client, model=self.config.judge_model)
            return _JudgeScorer(judge)
        if spec.kind == "ragas":
            if not spec.metric:
                raise ConfigError(f"metric {spec.name!r}: kind=ragas requires metric name")
            from evalkit.adapters.ragas import RagasScorer  # noqa: PLC0415

            return _CallableScorer(RagasScorer(spec.metric).score)
        if spec.kind == "exact_match":
            return _CallableScorer(_exact_match)
        if spec.kind == "regex":
            if not spec.pattern:
                raise ConfigError(f"metric {spec.name!r}: kind=regex requires pattern")
            return _CallableScorer(_regex_scorer(spec.pattern))
        if spec.kind == "custom":
            fn = self.custom_scorers.get(spec.name)
            if fn is None:
                raise ConfigError(
                    f"metric {spec.name!r}: kind=custom but no scorer registered. "
                    "Use suite.register_scorer(name, fn) before run().",
                )
            return _CallableScorer(fn)
        raise ConfigError(f"unknown metric kind: {spec.kind!r}")


@dataclass(frozen=True, slots=True)
class SuiteResult:
    """Returned from :meth:`Suite.run`."""

    report: SuiteReport

    def render(self) -> None:
        self.report.render()

    def save(self, path: str | Path) -> Path:
        return self.report.save(path)


# ---------- scorer abstraction ---------------------------------------------


class _Scorer:
    def score_one(
        self,
        input_data: Mapping[str, Any],
        output_data: Mapping[str, Any],
        expected: Mapping[str, Any] | None,
    ) -> tuple[float, Mapping[str, Any]]:
        raise NotImplementedError


@dataclass
class _JudgeScorer(_Scorer):
    judge: Judge

    def score_one(
        self,
        input_data: Mapping[str, Any],
        output_data: Mapping[str, Any],
        expected: Mapping[str, Any] | None,
    ) -> tuple[float, Mapping[str, Any]]:
        verdict = self.judge.score(
            input_data=input_data,
            output_data=output_data,
            expected=expected,
        )
        return verdict.score, {
            "criterion_scores": dict(verdict.criterion_scores),
            "reasoning": verdict.reasoning,
        }


@dataclass
class _CallableScorer(_Scorer):
    fn: ScorerFn

    def score_one(
        self,
        input_data: Mapping[str, Any],
        output_data: Mapping[str, Any],
        expected: Mapping[str, Any] | None,
    ) -> tuple[float, Mapping[str, Any]]:
        return float(self.fn(input_data, output_data, expected)), {}


# ---------- helpers --------------------------------------------------------


def _run_metric_parallel(
    *,
    spec: MetricSpec,  # noqa: ARG001, kept for caller symmetry / future per-metric logging
    scorer: _Scorer,
    dataset: GoldenDataset,
    preds: dict[str, PredictionRow],
    parallelism: int,
) -> list[Sample]:
    samples: list[Sample] = [None] * len(dataset)  # type: ignore[list-item]

    def _score_row(idx_row: tuple[int, Any]) -> tuple[int, Sample]:
        idx, row = idx_row
        pred = preds[row.id]
        score, detail = scorer.score_one(row.input, pred.output, row.expected)
        return idx, Sample(row_id=row.id, score=score, detail=detail)

    with ThreadPoolExecutor(max_workers=parallelism) as pool:
        for idx, sample in pool.map(_score_row, enumerate(dataset)):
            samples[idx] = sample
    return [s for s in samples if s is not None]


def _load_predictions(path: Path) -> dict[str, PredictionRow]:
    out: dict[str, PredictionRow] = {}
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            row = PredictionRow.model_validate(obj)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise EvalKitError(f"{path}:{lineno}: invalid prediction row: {exc}") from exc
        if row.id in out:
            raise EvalKitError(f"{path}:{lineno}: duplicate prediction id {row.id!r}")
        out[row.id] = row
    return out


def _self_pred(dataset: GoldenDataset) -> dict[str, PredictionRow]:
    """When no predictions file is provided, score the dataset's ``expected`` field as if
    it were the system output. Mainly useful for self-tests of judges and for
    static datasets where the answer is fixed.
    """
    return {row.id: PredictionRow(id=row.id, output=row.expected or {}) for row in dataset}


def _check_alignment(dataset: GoldenDataset, preds: dict[str, PredictionRow]) -> None:
    missing = [row.id for row in dataset if row.id not in preds]
    if missing:
        sample = ", ".join(missing[:5])
        suffix = "" if len(missing) <= 5 else f" (and {len(missing) - 5} more)"
        raise EvalKitError(f"predictions missing for ids: {sample}{suffix}")


def _exact_match(
    _input: Mapping[str, Any],
    output: Mapping[str, Any],
    expected: Mapping[str, Any] | None,
) -> float:
    if expected is None:
        return 0.0
    return 1.0 if output == expected else 0.0


_REGEX_INPUT_MAX = 16 * 1024  # 16 KB. bounds ReDoS worst case to <1s


def _regex_scorer(pattern: str) -> ScorerFn:
    """Build a regex scorer with bounded input size.

    Pattern length is already capped by ``MetricSpec`` validation. We
    additionally truncate the *input* the regex runs against, so a
    catastrophic-backtracking pattern combined with a long PR-supplied
    output can't pin a CI worker for minutes. Real LLM outputs are well
    under 16 KB; truncation is invisible in practice.
    """
    rx = re.compile(pattern)

    def _score(
        _input: Mapping[str, Any],
        output: Mapping[str, Any],
        _expected: Mapping[str, Any] | None,
    ) -> float:
        text = json.dumps(output)
        if len(text) > _REGEX_INPUT_MAX:
            text = text[:_REGEX_INPUT_MAX]
        return 1.0 if rx.search(text) else 0.0

    return _score


def _git_sha(base_dir: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(base_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None
    return out.stdout.strip() or None
