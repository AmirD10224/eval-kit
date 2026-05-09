# Quickstart

You'll have an eval suite running in 10 minutes.

## Install

```bash
pip install evalkit-oss
# or with optional integrations
pip install "evalkit-oss[ragas,langfuse]"
```

EvalKit needs Python 3.12+.

## Set your API key

The default judge is Claude Haiku 4.5. Set:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

(Don't have one? You can run everything offline with `--stub`. See
[the LLM-as-judge guide](concepts/llm-as-judge.md#offline-mode).)

## A minimal end-to-end run

We'll use the bundled QA-RAG example. From the repo root (or anywhere with
its `examples/qa-rag/` copied in):

```bash
cd examples/qa-rag

# 1. Validate the dataset and check inter-rater agreement.
evalkit dataset validate golden.jsonl
evalkit dataset agreement golden.jsonl
# → cohen kappa = 1.000 over 30 rated rows (2 raters)

# 2. Calibrate the judge against the human labels.
evalkit judge calibrate \
    --rubric rubrics/faithfulness.yaml \
    --golden golden.jsonl
# → JSON report, cohen_kappa, bias audit, "passes": true.

# 3. Run the suite.
evalkit run --suite suite.yaml --output current.json
```

Terminal output:

```
                       EvalKit suite: qa-rag
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━┳━━━━━━━━┳━━━━━━━━┓
┃ metric          ┃ kind    ┃ mean  ┃ n ┃ target ┃ status ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━╇━━━━━━━━╇━━━━━━━━┩
│ faithfulness    │ judge   │ 0.847 │ 30│ 0.700  │   ✓    │
│ idk_when_no_ctx │ regex   │ 0.967 │ 30│ 0.900  │   ✓    │
│ closed_book     │ exact   │ 0.733 │ 30│ 0.500  │   ✓    │
└─────────────────┴─────────┴───────┴───┴────────┴────────┘
```

## Add it to CI

Drop this into `.github/workflows/eval.yml`:

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
          suite: examples/qa-rag/suite.yaml
          baseline: main
          fail-on-regression: 5
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

Now any PR that drops a metric by more than 5pp will get a comment showing
the diff and a failing check. See the [GitHub Action guide](guides/github-action.md)
for the full surface area.

## Where next?

- [Calibration](concepts/calibration.md), what makes the judge trustworthy.
- [Synthetic data](concepts/synthetic-data.md), the taxonomy approach.
- [Custom judges](guides/custom-judge.md), plug in a non-Claude backend.
