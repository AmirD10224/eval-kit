# eval-kit

[![PyPI](https://img.shields.io/pypi/v/evalkit-oss.svg)](https://pypi.org/project/evalkit-oss/)
[![Python](https://img.shields.io/pypi/pyversions/evalkit-oss.svg)](https://pypi.org/project/evalkit-oss/)
[![CI](https://github.com/AmirD10224/eval-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/AmirD10224/eval-kit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-mkdocs--material-526CFE.svg)](https://AmirD10224.github.io/eval-kit/)

A small library for running LLM evals in CI. It does four things: generate synthetic adversarial examples, calibrate an LLM-as-judge against your human labels, run a suite over your app's outputs in parallel, and diff the result against a baseline so the PR fails when something regresses. There's a GitHub Action that wires it all up.

It's mostly glue around tools you've probably already heard of (Ragas, Inspect AI, promptfoo) plus the connective tissue I kept rewriting on every project: bias-tested judges, JSONL goldens with git-friendly diffs, and a regression gate that posts a sticky PR comment.

```bash
pip install evalkit-oss
```

## What a run looks like

```python
from evalkit.judges import CalibratedJudge
from evalkit.runner import Suite

# 1. Calibrate the judge against your golden set.
judge = CalibratedJudge.from_rubric("rubrics/faithfulness.yaml")
report = judge.calibrate("golden.jsonl")
assert report.cohen_kappa >= 0.7  # don't deploy a judge that disagrees with humans

# 2. Run the suite over your predictions.
suite = Suite.from_yaml("suites/main.yaml")
result = suite.run(predictions="predictions.jsonl")
result.save("current.json")
```

In CI:

```bash
$ evalkit diff --baseline baseline.json --current current.json --threshold 5
✓ answer_relevancy   0.812 → 0.835 (+2.3pp)
✓ closed_book        0.733 → 0.733 (+0.0pp)
✗ faithfulness       0.847 → 0.713 (-13.4pp)
✓ idk_when_no_ctx    0.967 → 0.967 (+0.0pp)
✗ regression detected
# (process exits 1)
```

## What it has that hand-rolled scripts don't

| | eval-kit | hand-rolled | Ragas alone | promptfoo alone |
| --- | :---: | :---: | :---: | :---: |
| Calibrated LLM-judge (Cohen's kappa ≥ 0.7) | ✓ | ✗ | ✗ | ✗ |
| Position / length / self-pref bias tests | ✓ | ✗ | ✗ | ✗ |
| Multi-rater agreement (kappa, Fleiss') | ✓ | ✗ | ✗ | ✗ |
| Synthetic adversarial data with provenance | ✓ | partial | ✗ | partial |
| Regression detection in CI | ✓ | partial | ✗ | partial |
| GitHub Action that blocks the PR | ✓ | ✗ | ✗ | ✗ |
| Works alongside Ragas + Inspect + promptfoo | ✓ | ✗ | own | own |

The point isn't that the other tools are bad, it's that you usually end up writing the connective tissue yourself, and that's what this is.

## GitHub Action

```yaml
name: eval
on: [pull_request]
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: AmirD10224/eval-kit@v0.1.0
        with:
          suite: suites/main.yaml
          baseline: main
          fail-on-regression: 5  # percentage points
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

When a PR drops `faithfulness` by 13.4 points on the sample app, the action posts a sticky comment with the diff and fails the check. There's a Playwright-rendered facsimile in [`docs/screenshots/auto-reject.png`](docs/screenshots/auto-reject.png), the Markdown is byte-identical to what the action posts on a real PR. [`docs/guides/real-pr-demo.md`](docs/guides/real-pr-demo.md) walks through capturing the live version.

## What's in the package

- `evalkit synth generate`, taxonomy-based synthetic data: edge cases, jailbreaks, multi-turn, PII probes, distribution shift. Provenance tracked. [docs](docs/concepts/synthetic-data.md)
- `evalkit dataset add | validate`, versioned JSONL golden datasets with schema validation and inter-rater agreement (Cohen's and Fleiss' kappa). [docs](docs/concepts/golden-datasets.md)
- `evalkit.judges.CalibratedJudge`. YAML rubric in, calibrated judge out, with bias auditing. Refuses to deploy when kappa drops below 0.7. [docs](docs/concepts/calibration.md)
- `evalkit run`, parallel suite runner with a Rich terminal output and a JSON report. [docs](docs/concepts/runner.md)
- `evalkit diff`, regression detector with per-metric thresholds. [docs](docs/concepts/regression-detection.md)
- GitHub Action [docs](docs/guides/github-action.md)
- Adapters for Ragas, Inspect AI, promptfoo (built-in), [Langfuse](docs/guides/langfuse-integration.md), and [Braintrust](docs/guides/braintrust-integration.md).

## Install

```bash
pip install evalkit-oss                    # core
pip install "evalkit-oss[ragas]"           # + Ragas metrics
pip install "evalkit-oss[langfuse]"        # + Langfuse trace pull
pip install "evalkit-oss[braintrust]"      # + Braintrust backend
pip install "evalkit-oss[all]"             # everything
```

Set `ANTHROPIC_API_KEY` for the default Haiku 4.5 judge. Plug in your own provider via [the custom-judge guide](docs/guides/custom-judge.md).

## Quickstart

```bash
git clone https://github.com/AmirD10224/eval-kit.git
cd eval-kit/examples/qa-rag
evalkit dataset validate golden.jsonl
evalkit run --suite suite.yaml --output current.json
evalkit diff --baseline baseline.json --current current.json
```

The longer walkthrough is in [the docs](https://AmirD10224.github.io/eval-kit/quickstart/).

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                          evalkit CLI                             │
└────────────────────────┬─────────────────────────────────────────┘
                         │
        ┌────────────────┼─────────────────┬───────────────┐
        ▼                ▼                 ▼               ▼
   ┌─────────┐     ┌──────────┐     ┌─────────────┐   ┌────────┐
   │  synth  │     │ dataset  │     │   judges    │   │ runner │
   │(taxonomy)│    │(JSONL+git)│    │(calibrated) │   │(parallel)│
   └─────────┘     └──────────┘     └──────┬──────┘   └────┬───┘
                                           │                │
                                           ▼                ▼
                                    ┌─────────────┐   ┌──────────┐
                                    │     llm     │   │   diff   │
                                    │ (Anthropic) │   │(regress.) │
                                    └─────────────┘   └──────────┘
                                                            │
                                                            ▼
                                                   ┌─────────────┐
                                                   │  ci/github  │
                                                   │ (PR comment)│
                                                   └─────────────┘
   Adapters: Ragas · Inspect AI · promptfoo · Langfuse · Braintrust
```

## Status

- 0.1.0, first public release. The public API may shift before 1.0.
- Tested on Python 3.12 and 3.13.
- 87% branch coverage (gate set at 85%), mypy strict, ruff clean.

## License

[MIT](LICENSE).

## Citation

```bibtex
@software{dhibi_evalkit_2026,
  author = {Dhibi, Amir},
  title  = {eval-kit: an LLM eval harness},
  year   = {2026},
  url    = {https://github.com/AmirD10224/eval-kit}
}
```
