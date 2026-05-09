"use client";

import { useEffect, useState } from "react";
import { ArrowRight, ArrowUpRight, Check, Copy, Github } from "lucide-react";
import { CodeBlock } from "@/components/code-block";
import { CalibrationPlot, Sparkline, TaxBars } from "@/components/charts";
import { DiffTable } from "@/components/diff-table";
import { PrComment } from "@/components/pr-comment";

const PITCH_CODE = `from evalkit.judges import CalibratedJudge
from evalkit.runner import Suite

# 1. Load a YAML rubric, calibrate it against your golden set.
judge = CalibratedJudge.from_rubric("rubrics/faithfulness.yaml")
report = judge.calibrate("golden.jsonl")
assert report.cohen_kappa >= 0.7, "judge disagrees with humans"

# 2. Run a suite over your app's outputs in parallel, get a JSON report.
suite = Suite.from_yaml("suites/main.yaml")
result = suite.run(predictions="predictions.jsonl")
result.save("current.json")

# 3. In CI, diff against main and fail the PR on regressions.
#    (Or just use the GitHub Action, see below.)`;

export default function Page() {
  return (
    <div className="space-y-32 md:space-y-40 py-20 md:py-28">
      {/* HERO */}
      <section className="text-center max-w-3xl mx-auto fade-up">
        <span className="pill pill-accent mb-8 inline-flex">
          v0.1.0 · live on PyPI
        </span>

        <h1
          className="display display-tight text-balance"
          style={{ fontSize: "clamp(44px, 7.5vw, 84px)" }}
        >
          An LLM eval harness that fits in CI.
        </h1>

        <p className="mt-8 mx-auto max-w-2xl text-[17px] leading-[1.55] text-[var(--color-fg-mute)]">
          A small Python library: calibrated LLM-as-judge, synthetic adversarial
          examples with provenance, a regression diff that fails the PR.
          There&rsquo;s a GitHub Action that wires it together. Ragas, Inspect
          AI, and promptfoo plug in via adapters.
        </p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <a href="#install" className="btn-primary">
            Install
            <ArrowRight className="size-4" />
          </a>
          <a
            href="https://github.com/AmirD10224/eval-kit"
            target="_blank"
            rel="noreferrer"
            className="btn-secondary"
          >
            <Github className="size-4" />
            GitHub
          </a>
        </div>

        <div className="mt-20 flex flex-wrap justify-center gap-x-12 gap-y-6">
          <Stat big="κ ≥ 0.7" label="Calibrated judge" />
          <Stat big="161" label="Tests passing" />
          <Stat big="87%" label="Coverage" />
          <Stat big="MIT" label="Licence" />
        </div>
      </section>

      {/* INSTALL */}
      <section id="install" className="max-w-3xl mx-auto fade-up">
        <p className="eyebrow text-center mb-6">Install</p>
        <h2
          className="display text-balance text-center mb-10"
          style={{ fontSize: "clamp(28px, 3.6vw, 40px)" }}
        >
          Pick one.
        </h2>
        <div className="space-y-3">
          <InstallTile cmd="pip install evalkit-oss" label="from PyPI · stable" />
          <InstallTile cmd="uv add evalkit-oss" label="from PyPI · uv" />
          <InstallTile cmd="evalkit synth generate" label="first command · ≈ 5s" />
        </div>
      </section>

      {/* PITCH */}
      <section id="pitch" className="fade-up">
        <header className="max-w-2xl mb-10">
          <p className="eyebrow mb-3">Usage</p>
          <h2
            className="display display-tight"
            style={{ fontSize: "clamp(32px, 4.5vw, 56px)" }}
          >
            Calibrate the judge, run the suite,{" "}
            <span className="text-[var(--color-accent)]">diff in CI</span>.
          </h2>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <div className="lg:col-span-7">
            <CodeBlock code={PITCH_CODE} highlightLines={[5, 9, 13]} />
          </div>
          <ol className="lg:col-span-5 space-y-6 lg:pl-2">
            <PitchStep
              n="01"
              title="Calibrate the judge"
              body="A YAML rubric and your golden set in. A reliability score (Cohen's κ) out. The judge refuses to deploy if it disagrees with humans."
            />
            <PitchStep
              n="02"
              title="Run the suite"
              body="A parallel runner over your app's predictions. Strict Pydantic at every boundary. JSON report with provenance, retries, parallelism."
            />
            <PitchStep
              n="03"
              title="Diff in CI"
              body="Current vs baseline. Configurable per-metric thresholds. Regression in any one of them fails the check, automatically."
            />
          </ol>
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="fade-up">
        <header className="max-w-2xl mb-12">
          <p className="eyebrow mb-3">What&rsquo;s in it</p>
          <h2
            className="display display-tight"
            style={{ fontSize: "clamp(32px, 4.5vw, 56px)" }}
          >
            Four modules.
          </h2>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-[var(--color-line)] border border-[var(--color-line)] rounded-[14px] overflow-hidden">
          <Feature
            tag="evalkit.judges"
            title="Calibrated LLM-as-judge"
            body="YAML rubric → calibrated judge with bias auditing for position, length, and self-preference. Refuses to deploy when Cohen's κ < 0.7."
          >
            <div className="card-hi p-4">
              <div className="flex items-baseline justify-between mb-3">
                <p className="text-[10.5px] font-mono uppercase tracking-[0.16em] text-[var(--color-fg-sub)]">
                  Reliability · κ vs humans
                </p>
                <p className="display tabular text-[var(--color-fg)]" style={{ fontSize: 22 }}>
                  κ · 0.81
                </p>
              </div>
              <CalibrationPlot />
            </div>
          </Feature>

          <Feature
            tag="evalkit.synth"
            title="Synthetic adversarial data"
            body="Taxonomy-based generation, edge cases, jailbreaks, multi-turn, PII probes, distribution shift, with provenance tracking."
          >
            <div className="card-hi p-4">
              <div className="flex items-baseline justify-between mb-3">
                <p className="text-[10.5px] font-mono uppercase tracking-[0.16em] text-[var(--color-fg-sub)]">
                  Generated · last suite
                </p>
                <p className="display tabular text-[var(--color-fg)]" style={{ fontSize: 22 }}>
                  240
                </p>
              </div>
              <TaxBars
                bins={[42, 36, 31, 28, 41, 24, 38]}
                labels={["EDGE", "JAIL", "PII", "MULT", "SHIFT", "AMBI", "OOD"]}
                height={68}
                highlight={4}
              />
            </div>
          </Feature>

          <Feature
            tag="evalkit diff"
            title="Regression detection"
            body="Diff vs baseline. Configurable per-metric threshold. Sticky PR comment posts the delta. Failures block merge."
          >
            <div className="card-hi p-4 space-y-3">
              <div className="flex items-baseline justify-between">
                <p className="text-[10.5px] font-mono uppercase tracking-[0.16em] text-[var(--color-fg-sub)]">
                  Faithfulness · 30 days
                </p>
                <p className="display tabular text-[var(--color-danger)]" style={{ fontSize: 22 }}>
                  -13.4pp
                </p>
              </div>
              <Sparkline
                data={[0.81, 0.83, 0.84, 0.85, 0.84, 0.86, 0.85, 0.85, 0.84, 0.83, 0.71]}
                color="var(--color-accent)"
                height={56}
              />
              <p className="text-[11px] font-mono text-[var(--color-fg-sub)]">
                ▸ baseline 0.847 → current 0.713
              </p>
            </div>
          </Feature>

          <Feature
            tag=".github/workflows/eval.yml"
            title="GitHub Action that auto-rejects"
            body="One YAML, three lines. Posts a sticky regression report to your PR and blocks merge until the model is fixed or thresholds are adjusted."
          >
            <div className="card-hi p-4">
              <pre className="font-mono text-[11.5px] leading-[1.65] text-[var(--color-fg-dim)] whitespace-pre-wrap">
{`- uses: AmirD10224/eval-kit@v0.1.0
  with:
    suite: suites/main.yaml
    baseline: main
    fail-on-regression: 5`}
              </pre>
              <p className="mt-3 pt-3 border-t border-[var(--color-line)] text-[11px] font-mono text-[var(--color-fg-sub)]">
                ▸ ≈ 30s overhead · cached calibration
              </p>
            </div>
          </Feature>
        </div>
      </section>

      {/* DIFF DEMO */}
      <section className="fade-up">
        <header className="max-w-2xl mb-10">
          <p className="eyebrow mb-3">In CI</p>
          <h2
            className="display display-tight"
            style={{ fontSize: "clamp(32px, 4.5vw, 56px)" }}
          >
            When <span className="text-[var(--color-danger)]">faithfulness</span> drops 13 points,
            the PR check fails. Sticky comment, exit 1.
          </h2>
        </header>
        <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] gap-4">
          <DiffTable />
          <PrComment />
        </div>
      </section>

      {/* COMPARISON */}
      <section className="fade-up">
        <header className="max-w-2xl mb-10">
          <p className="eyebrow mb-3">Comparison</p>
          <h2
            className="display display-tight"
            style={{ fontSize: "clamp(32px, 4.5vw, 56px)" }}
          >
            What it covers, that nothing else does.
          </h2>
        </header>
        <ComparisonTable />
      </section>

      {/* CTA */}
      <section className="fade-up text-center max-w-2xl mx-auto">
        <p className="eyebrow mb-3">Get it</p>
        <h2
          className="display display-tight text-balance"
          style={{ fontSize: "clamp(36px, 5.5vw, 72px)" }}
        >
          One pip command and a YAML file.
        </h2>
        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <CopyableCommand command="pip install evalkit-oss" />
          <a
            href="https://github.com/AmirD10224/eval-kit"
            target="_blank"
            rel="noreferrer"
            className="btn-secondary"
          >
            <ArrowUpRight className="size-4" />
            Read on GitHub
          </a>
        </div>
      </section>
    </div>
  );
}

/* ─── Components ─── */

function Stat({ big, label }: { big: string; label: string }) {
  return (
    <div>
      <p className="display tabular text-[var(--color-fg)]" style={{ fontSize: 32 }}>
        {big}
      </p>
      <p className="mt-2 text-[12px] font-mono uppercase tracking-[0.16em] text-[var(--color-fg-sub)]">
        {label}
      </p>
    </div>
  );
}

function PitchStep({
  n,
  title,
  body,
}: {
  n: string;
  title: string;
  body: string;
}) {
  return (
    <li className="flex gap-5 items-start">
      <span className="text-[15px] font-mono tabular text-[var(--color-accent)] shrink-0 mt-0.5">
        {n}
      </span>
      <div className="min-w-0">
        <p className="text-[16px] font-semibold tracking-tight text-[var(--color-fg)]">
          {title}
        </p>
        <p className="mt-1.5 text-[13.5px] leading-[1.55] text-[var(--color-fg-mute)]">
          {body}
        </p>
      </div>
    </li>
  );
}

function Feature({
  tag,
  title,
  body,
  children,
}: {
  tag: string;
  title: string;
  body: string;
  children: React.ReactNode;
}) {
  return (
    <article className="bg-[var(--color-bg)] p-7 md:p-9 flex flex-col gap-5 hover:bg-[var(--color-bg-2)] transition-colors">
      <div>
        <p className="text-[11px] font-mono text-[var(--color-fg-sub)] mb-2">
          {tag}
        </p>
        <h3 className="text-[20px] font-semibold tracking-tight text-[var(--color-fg)] leading-tight">
          {title}
        </h3>
        <p className="mt-3 text-[14px] leading-[1.55] text-[var(--color-fg-mute)] max-w-md">
          {body}
        </p>
      </div>
      <div className="mt-auto pt-2">{children}</div>
    </article>
  );
}

function InstallTile({ cmd, label }: { cmd: string; label: string }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const id = setTimeout(() => setCopied(false), 1400);
    return () => clearTimeout(id);
  }, [copied]);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(cmd);
        setCopied(true);
      }}
      className="card group w-full px-5 py-3.5 text-left flex items-center gap-4 hover:border-[var(--color-line-hi)] transition-colors"
    >
      <span className="text-[var(--color-accent)] font-mono text-[15px]">$</span>
      <span className="font-mono text-[15px] text-[var(--color-fg)] tabular flex-1">
        {cmd}
      </span>
      <span className="text-[11px] font-mono text-[var(--color-fg-sub)] hidden sm:inline">
        {label}
      </span>
      <span className="text-[var(--color-fg-sub)] group-hover:text-[var(--color-fg)] transition-colors">
        {copied ? <Check className="size-4" strokeWidth={2.5} /> : <Copy className="size-4" />}
      </span>
    </button>
  );
}

function CopyableCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const id = setTimeout(() => setCopied(false), 1400);
    return () => clearTimeout(id);
  }, [copied]);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(command);
        setCopied(true);
      }}
      className="btn-primary"
    >
      <span className="text-[var(--color-fg-sub)] font-mono mr-1">$</span>
      <span className="font-mono">{command}</span>
      {copied ? <Check className="size-4" strokeWidth={2.5} /> : <Copy className="size-4" />}
    </button>
  );
}

function ComparisonTable() {
  const COLS = ["EvalKit", "Hand-rolled", "Ragas", "promptfoo"] as const;
  const ROWS: { feature: string; cells: (boolean | "partial")[] }[] = [
    { feature: "Calibrated LLM-judge (κ ≥ 0.7)", cells: [true, false, false, false] },
    { feature: "Position / length / self-pref bias tests", cells: [true, false, false, false] },
    { feature: "Multi-rater agreement (κ, Fleiss')", cells: [true, false, false, false] },
    { feature: "Synthetic adversarial data (taxonomy)", cells: [true, "partial", false, "partial"] },
    { feature: "Regression detection in CI", cells: [true, "partial", false, "partial"] },
    { feature: "GitHub Action that blocks the PR", cells: [true, false, false, false] },
    { feature: "Works with Ragas + Inspect + promptfoo", cells: [true, false, "partial", "partial"] },
  ];
  return (
    <div className="card overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[var(--color-line)]">
            <th className="text-left px-6 py-4 text-[11px] uppercase tracking-[0.16em] font-mono text-[var(--color-fg-sub)] font-medium">
              Feature
            </th>
            {COLS.map((c, i) => (
              <th
                key={c}
                className={`text-center px-3 py-4 text-[11px] uppercase tracking-[0.16em] font-mono font-medium ${i === 0 ? "text-[var(--color-accent)]" : "text-[var(--color-fg-sub)]"}`}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row, ri) => (
            <tr
              key={ri}
              className={`${ri < ROWS.length - 1 ? "border-b border-[var(--color-line)]" : ""} hover:bg-[var(--color-bg-2)] transition-colors`}
            >
              <td className="px-6 py-3.5 text-[13.5px] text-[var(--color-fg)]">
                {row.feature}
              </td>
              {row.cells.map((v, ci) => (
                <td key={ci} className="px-3 py-3.5 text-center">
                  {v === true ? (
                    <Check className="size-4 mx-auto text-[var(--color-success)]" strokeWidth={2.5} />
                  ) : v === "partial" ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-[var(--color-bg-3)] border border-[var(--color-line-2)] text-[10.5px] font-mono uppercase tracking-tight text-[var(--color-fg-mute)]">
                      partial
                    </span>
                  ) : (
                    <span className="text-[var(--color-fg-faint)]">-</span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
