# Regression detection

`evalkit diff --baseline a.json --current b.json --threshold 5` is the core
of the CI story.

## The model

A "regression" is a per-metric move bigger than `--threshold` percentage
points in the *bad* direction. The bad direction is read from each metric's
`higher_is_better` field (default `true`).

For metrics where higher is better (faithfulness, accuracy, …):

```
delta = mean_current - mean_baseline
is_regression = (delta * 100) < -threshold_pp
```

For metrics where lower is better (latency, error rate, …):

```
is_regression = (delta * 100) > threshold_pp
```

## Output

```bash
$ evalkit diff --baseline baseline.json --current current.json --threshold 5
✗ faithfulness          0.847 → 0.713 (-13.4pp)
✓ answer_relevancy      0.812 → 0.835 (+2.3pp)
✓ closed_book           0.733 → 0.733 (+0.0pp)
✓ idk_when_no_ctx       0.967 → 0.967 (+0.0pp)
✗ regression detected
exit 1
```

Add `--markdown comment.md` and `--json-out diff.json` to emit machine-
readable artifacts. The Markdown is what the GitHub Action posts on the PR.

## Picking a threshold

Most teams start at **5pp** and tighten over time as their golden set grows
and their judge calibration improves.

Considerations:

- **Variance.** Run your suite three times on the same code; the spread
  is the floor of your threshold. If your judge is noisy enough that two
  runs differ by 6pp, a 5pp threshold will fire false alarms.
- **Sample size.** With 30 samples, a real 5pp regression has ~15%
  detection probability at 1-σ noise. Bigger golden sets buy you tighter
  thresholds.
- **Stakes.** Safety-relevant metrics warrant 1–2pp; helpfulness-style
  metrics tolerate 5–10pp.

## Multiple metrics

A regression in *any* tracked metric fails the PR. To exclude a metric from
the gate, drop it from the suite (it'll still run, but won't gate).
