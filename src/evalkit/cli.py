"""``evalkit`` command-line interface, built with Click.

Verbs::

    evalkit synth generate --task QA --schema schema.yaml --count 200
    evalkit dataset add --case row.json --to golden.jsonl
    evalkit dataset validate golden.jsonl
    evalkit dataset agreement golden.jsonl
    evalkit run --suite suite.yaml --output report.json
    evalkit diff --baseline baseline.json --current current.json
    evalkit judge calibrate --rubric rubric.yaml --golden golden.jsonl

Every verb is scriptable; every verb returns 0/1 in a way the GitHub Action
can use for ``fail-on-regression``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml
from rich.console import Console

from evalkit._version import __version__
from evalkit.dataset.agreement import compute_agreement
from evalkit.dataset.store import GoldenDataset
from evalkit.diff.differ import diff_reports
from evalkit.exceptions import EvalKitError
from evalkit.runner.report import SuiteReport
from evalkit.runner.runner import Suite

console = Console()


@click.group(help="EvalKit, production-grade eval harness for LLM apps.")
@click.version_option(__version__, prog_name="evalkit")
def main() -> None:
    """Top-level group."""


# ---------- synth ----------------------------------------------------------


@main.group()
def synth() -> None:
    """Synthetic test-case generation."""


@synth.command("generate")
@click.option("--task", required=True, help="Free-text task description.")
@click.option(
    "--schema",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="YAML/JSON file describing the input schema.",
)
@click.option("--count", type=int, default=50, show_default=True)
@click.option(
    "--categories",
    help="Comma-separated taxonomy categories (default: all).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("synth.jsonl"),
    show_default=True,
)
@click.option(
    "--stub/--no-stub",
    default=False,
    help="Use the deterministic stub client (offline; for testing).",
)
@click.option("--seed", type=int, default=42, show_default=True)
def synth_generate(
    task: str,
    schema: Path,
    count: int,
    categories: str | None,
    output: Path,
    stub: bool,
    seed: int,
) -> None:
    """Generate adversarial test cases via the configured taxonomy."""
    from evalkit.llm.client import AnthropicClient
    from evalkit.llm.stub import StubClient
    from evalkit.synth.generator import SynthGenerator, SynthRequest
    from evalkit.synth.taxonomy import TaxonomyCategory

    schema_dict = yaml.safe_load(schema.read_text(encoding="utf-8")) or {}
    cat_tuple = (
        tuple(TaxonomyCategory(c.strip()) for c in categories.split(",")) if categories else None
    )
    client = StubClient() if stub else AnthropicClient()
    generator = SynthGenerator(client=client)
    rows = generator.generate(
        SynthRequest(
            task=task,
            schema=schema_dict,
            count=count,
            categories=cat_tuple,
            seed=seed,
        ),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row))
            f.write("\n")
    console.print(f"[green]✓[/green] wrote {len(rows)} rows → {output}")


# ---------- dataset --------------------------------------------------------


@main.group()
def dataset() -> None:
    """Golden-dataset management."""


@dataset.command("validate")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def dataset_validate(path: Path) -> None:
    """Validate a JSONL dataset against the schema."""
    n = GoldenDataset.validate_file(path)
    console.print(f"[green]✓[/green] {path}: {n} rows valid")


@dataset.command("add")
@click.option(
    "--case",
    "case_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--to",
    "to_path",
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
)
def dataset_add(case_path: Path, to_path: Path) -> None:
    """Append a single case (JSON file) to a JSONL dataset."""
    case = json.loads(case_path.read_text(encoding="utf-8"))
    ds = GoldenDataset.load(to_path) if to_path.exists() else GoldenDataset([], path=to_path)
    ds.add(case)
    ds.save()
    console.print(f"[green]✓[/green] added {case.get('id', '?')} → {to_path}")


@dataset.command("agreement")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--low-threshold", type=float, default=1.0, show_default=True)
def dataset_agreement(path: Path, low_threshold: float) -> None:
    """Report inter-rater agreement on a labelled dataset."""
    ds = GoldenDataset.load(path)
    report = compute_agreement(ds, low_threshold=low_threshold)
    console.print(
        f"{report.statistic} kappa = [bold]{report.kappa:.3f}[/bold] over "
        f"{report.n_rated_rows} rated rows ({report.n_raters} raters)",
    )
    if report.low_agreement_ids:
        console.print(
            f"[yellow]⚠ low-agreement rows ({len(report.low_agreement_ids)}):"
            f"[/yellow] {', '.join(report.low_agreement_ids[:10])}",
        )


# ---------- run ------------------------------------------------------------


@main.command("run")
@click.option(
    "--suite",
    "suite_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--predictions",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("report.json"),
    show_default=True,
)
@click.option(
    "--stub/--no-stub",
    default=False,
    help="Use the deterministic stub client (offline; for testing).",
)
def run_suite(
    suite_path: Path,
    predictions: Path | None,
    output: Path,
    stub: bool,
) -> None:
    """Run an eval suite and write a JSON report."""
    from evalkit.llm.client import AnthropicClient
    from evalkit.llm.stub import StubClient, echo_score_from_prompt

    client = (
        StubClient(scorer=echo_score_from_prompt(), default_response='{"score": 4}')
        if stub
        else AnthropicClient()
    )
    suite = Suite.from_yaml(suite_path)
    # Pass the predictions path absolute so it is interpreted as the user
    # typed it (CWD-relative), NOT re-resolved against the suite directory.
    pred_arg = predictions.resolve() if predictions is not None else None
    result = suite.run(predictions=pred_arg, client=client)
    result.render()
    out = result.save(output)
    console.print(f"[green]✓[/green] report → {out}")


# ---------- diff -----------------------------------------------------------


@main.command("diff")
@click.option(
    "--baseline",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--current",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option("--threshold", type=float, default=5.0, show_default=True)
@click.option(
    "--markdown",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the PR-comment Markdown to this file.",
)
@click.option(
    "--json-out",
    "json_out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the structured diff JSON to this file.",
)
def diff_cmd(
    baseline: Path,
    current: Path,
    threshold: float,
    markdown: Path | None,
    json_out: Path | None,
) -> None:
    """Diff two suite reports; exit 1 if any metric regresses beyond --threshold."""
    from evalkit.ci.markdown import render_pr_comment

    base_report = SuiteReport.load(baseline)
    cur_report = SuiteReport.load(current)
    report = diff_reports(base_report, cur_report, threshold_pp=threshold)

    for d in report.deltas:
        sign = "+" if d.delta_pp >= 0 else ""
        marker = "[red]✗[/red]" if d.is_regression else "[green]✓[/green]"
        console.print(
            f"{marker} {d.name:<24} {d.baseline:.3f} → {d.current:.3f} ({sign}{d.delta_pp:.1f}pp)",
        )

    if markdown is not None:
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(render_pr_comment(report), encoding="utf-8")
        console.print(f"[dim]markdown → {markdown}[/dim]")
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        console.print(f"[dim]json → {json_out}[/dim]")

    if report.has_regressions:
        console.print("[bold red]✗ regression detected[/bold red]")
        sys.exit(1)
    console.print("[bold green]✓ no regressions[/bold green]")


# ---------- judge ----------------------------------------------------------


@main.group()
def judge() -> None:
    """LLM-judge calibration utilities."""


@judge.command("calibrate")
@click.option(
    "--rubric",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--golden",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--stub/--no-stub",
    default=False,
    help="Use the stub client (offline; for testing).",
)
@click.option("--no-bias-audit", "no_bias", is_flag=True, default=False)
def judge_calibrate(
    rubric: Path,
    golden: Path,
    stub: bool,
    no_bias: bool,
) -> None:
    """Calibrate a judge against a labelled golden set."""
    from evalkit.judges.calibrated import CalibratedJudge
    from evalkit.llm.client import AnthropicClient
    from evalkit.llm.stub import StubClient, echo_score_from_prompt

    client = (
        StubClient(scorer=echo_score_from_prompt(), default_response='{"score": 4}')
        if stub
        else AnthropicClient()
    )
    j = CalibratedJudge.from_rubric(rubric, client=client)
    report = j.calibrate(golden, run_bias_audit=not no_bias)
    console.print(json.dumps(report.to_dict(), indent=2))
    if not report.passes:
        sys.exit(1)


# ---------- entrypoint ------------------------------------------------------


def _entrypoint() -> None:
    try:
        main(standalone_mode=True)
    except EvalKitError as exc:
        console.print(f"[red]error:[/red] {exc}")
        sys.exit(2)


if __name__ == "__main__":  # pragma: no cover
    _entrypoint()
