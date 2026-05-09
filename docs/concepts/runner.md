# The eval runner

`evalkit run` loads a suite, a golden dataset, optionally a predictions
file, and computes every metric across all samples in parallel.

## The suite YAML

```yaml
name: qa-rag
description: Eval a RAG QA system
dataset: golden.jsonl
predictions: predictions.jsonl   # optional; otherwise we score `expected`
judge_model: claude-haiku-4-5-20251001
parallelism: 8
seed: 42

metrics:
  - name: faithfulness
    kind: judge
    rubric: rubrics/faithfulness.yaml
    target: 0.7

  - name: shape_check
    kind: regex
    pattern: '"answer"\s*:'

  - name: closed_book
    kind: exact_match
```

## Metric kinds

| `kind`        | What it does                                                  |
| ------------- | ------------------------------------------------------------- |
| `judge`       | YAML rubric → `CalibratedJudge`                              |
| `ragas`       | One of `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`, `context_relevancy`, `answer_correctness` |
| `exact_match` | `output == expected`                                          |
| `regex`       | regex search over the output (serialised as JSON)             |
| `custom`      | call a function registered via `Suite.register_scorer(...)`   |

## Programmatic API

```python
from evalkit import Suite

suite = Suite.from_yaml("suite.yaml")
suite.register_scorer("my_metric", my_scorer_fn)  # for kind: custom
result = suite.run(predictions="predictions.jsonl")
result.render()                          # rich table to stdout
result.save("current.json")              # JSON report for diff/CI
```

## Parallelism

The runner uses a thread pool sized by `parallelism:` (default 8). Each
metric runs sequentially across samples but the *samples* are parallel -
because the bottleneck is judge HTTP, not Python work.

If you need different parallelism per metric, run multiple suites.
