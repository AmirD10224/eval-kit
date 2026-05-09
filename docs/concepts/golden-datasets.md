# Golden datasets

A golden dataset is the most important artifact in your eval setup. EvalKit
stores them as **JSONL** (one row per line), validated against
:class:`evalkit.config.DatasetRow`, versioned with **git**.

## The row shape

```json
{
  "id": "qa-001",
  "input": { "question": "Capital of France?", "contexts": ["Paris is..."] },
  "expected": { "answer": "Paris" },
  "metadata": { "source": "manual" },
  "labels": [
    { "rater": "alice", "score": 5 },
    { "rater": "bob",   "score": 5 }
  ]
}
```

- `id`, unique, no whitespace.
- `input`, whatever shape your task uses; freeform mapping.
- `expected`, optional reference (the judge can use it; `exact_match`
  metrics require it).
- `metadata`, anything you want to filter on later.
- `labels`, zero or more rater dicts, used by `evalkit dataset agreement`
  and by judge calibration.

## Validate

```bash
evalkit dataset validate golden.jsonl
# → ✓ golden.jsonl: 30 rows valid
```

This catches: malformed JSON, missing required fields, duplicate ids,
whitespace in ids.

## Inter-rater agreement

```bash
evalkit dataset agreement golden.jsonl
# → cohen kappa = 0.83 over 30 rated rows (2 raters)
# → ⚠ low-agreement rows (3): qa-007, qa-011, qa-022
```

`evalkit dataset agreement` computes Cohen's κ for 2 raters and Fleiss' κ
for ≥3, and surfaces the row IDs where raters disagreed by more than the
configurable threshold. Fix those rows first.

## Versioning

EvalKit deliberately doesn't track its own version metadata; we use git.

```bash
git log --oneline golden.jsonl
git diff main golden.jsonl
git blame golden.jsonl   # who labeled which row
```

If you'd rather track per-row authorship in `metadata`, nothing stops you -
the schema accepts arbitrary keys there.
