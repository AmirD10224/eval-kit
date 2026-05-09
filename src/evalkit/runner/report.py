"""Suite-result data shapes + Rich-flavoured terminal renderer."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from evalkit.config import ReportEnvelope


@dataclass(frozen=True, slots=True)
class Sample:
    """One scored sample within a metric (input row + verdict)."""

    row_id: str
    score: float
    detail: Mapping[str, Any]


@dataclass(slots=True)
class MetricResult:
    """Aggregate result for one metric across all samples."""

    name: str
    kind: str
    mean: float
    n: int
    samples: list[Sample] = field(default_factory=list)
    higher_is_better: bool = True
    target: float | None = None

    def passes_target(self) -> bool:
        if self.target is None:
            return True
        return self.mean >= self.target if self.higher_is_better else self.mean <= self.target


@dataclass(slots=True)
class SuiteReport:
    """The full result of one suite run, both pretty-printable and serialisable."""

    suite_name: str
    metrics: list[MetricResult]
    n_samples: int
    judge_model: str
    timestamp: str
    duration_seconds: float
    seed: int
    git_sha: str | None = None

    # ---------- rendering ----------------------------------------------

    def render(self, console: Console | None = None) -> None:
        """Print a Rich table of the metrics."""
        c = console or Console()
        table = Table(title=f"EvalKit suite: {self.suite_name}", show_lines=False)
        table.add_column("metric", style="bold")
        table.add_column("kind")
        table.add_column("mean", justify="right")
        table.add_column("n", justify="right")
        table.add_column("target", justify="right")
        table.add_column("status", justify="center")
        for m in self.metrics:
            status = "✓" if m.passes_target() else "✗"
            target_str = "-" if m.target is None else f"{m.target:.3f}"
            table.add_row(
                m.name,
                m.kind,
                f"{m.mean:.3f}",
                str(m.n),
                target_str,
                f"[green]{status}[/green]" if status == "✓" else f"[red]{status}[/red]",
            )
        c.print(table)
        c.print(
            f"[dim]judge_model={self.judge_model} seed={self.seed} "
            f"duration={self.duration_seconds:.1f}s[/dim]",
        )

    # ---------- serialisation ------------------------------------------

    def to_envelope(self) -> ReportEnvelope:
        return ReportEnvelope(
            suite=self.suite_name,
            timestamp=self.timestamp,
            metrics={m.name: m.mean for m in self.metrics},
            n_samples=self.n_samples,
            judge_model=self.judge_model,
            git_sha=self.git_sha,
            seed=self.seed,
            duration_seconds=self.duration_seconds,
        )

    def to_dict(self) -> dict[str, Any]:
        env = self.to_envelope().model_dump()
        env["per_metric"] = {
            m.name: {
                "kind": m.kind,
                "mean": m.mean,
                "n": m.n,
                "target": m.target,
                "higher_is_better": m.higher_is_better,
            }
            for m in self.metrics
        }
        return env

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return p

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SuiteReport:
        per_metric = data.get("per_metric") or {}
        metrics = [
            MetricResult(
                name=name,
                kind=str(info.get("kind", "judge")),
                mean=float(info.get("mean", data["metrics"].get(name, 0.0))),
                n=int(info.get("n", data.get("n_samples", 0))),
                target=info.get("target"),
                higher_is_better=bool(info.get("higher_is_better", True)),
            )
            for name, info in per_metric.items()
        ]
        if not metrics:
            metrics = [
                MetricResult(name=name, kind="unknown", mean=float(value), n=0)
                for name, value in data["metrics"].items()
            ]
        return cls(
            suite_name=str(data["suite"]),
            metrics=metrics,
            n_samples=int(data["n_samples"]),
            judge_model=str(data["judge_model"]),
            timestamp=str(data["timestamp"]),
            duration_seconds=float(data["duration_seconds"]),
            seed=int(data["seed"]),
            git_sha=data.get("git_sha"),
        )

    @classmethod
    def load(cls, path: str | Path) -> SuiteReport:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
