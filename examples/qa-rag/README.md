# Example: evaluating a RAG QA app

A toy RAG system + a full EvalKit suite. Walks through:

1. A 30-row golden dataset (`golden.jsonl`) with two human raters per row.
2. A YAML faithfulness rubric (`rubrics/faithfulness.yaml`).
3. An `app.py` that produces predictions from the toy retriever.
4. A `suite.yaml` that runs three metrics: judge faithfulness, regex
   "I don't know" gate, and exact-match for closed-book questions.

## Run it

```bash
# from repo root
pip install -e ".[ragas]"
cd examples/qa-rag

# 1. Validate the golden set + check inter-rater agreement
evalkit dataset validate golden.jsonl
evalkit dataset agreement golden.jsonl

# 2. Calibrate the judge against humans
evalkit judge calibrate \
    --rubric rubrics/faithfulness.yaml \
    --golden golden.jsonl \
    --stub          # remove --stub to use real Claude

# 3. Generate predictions
python app.py > predictions.jsonl

# 4. Run the eval suite
evalkit run \
    --suite suite.yaml \
    --predictions predictions.jsonl \
    --output current.json \
    --stub          # remove --stub to use real Claude

# 5. (Optional) compare against a saved baseline
evalkit diff --baseline baseline.json --current current.json --threshold 5
```

## What you should see

Terminal output like:

```
EvalKit suite: qa-rag
┏━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━┳━━━━━━━━┳━━━━━━━━┓
┃ metric         ┃ kind   ┃ mean  ┃ n ┃ target ┃ status ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━╇━━━━━━━━╇━━━━━━━━┩
│ faithfulness   │ judge  │ 0.847 │ 30│ 0.700  │   ✓    │
│ idk_when_no_ctx│ regex  │ 1.000 │ 30│ 0.900  │   ✓    │
│ closed_book    │ exact  │ 0.733 │ 30│ 0.500  │   ✓    │
└────────────────┴────────┴───────┴───┴────────┴────────┘
```
