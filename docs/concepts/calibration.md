# Calibration

This is the page to read first. Every other concept in EvalKit makes sense
once you understand the calibration step.

## The problem

LLM-as-judge looks like a great idea: ask Claude (or GPT-4, or whatever)
"is this answer faithful to the context?" and read its score. It's cheap.
It's fast. It scales.

It also drifts. Judges show position bias, length bias, and self-preference
bias, and worst of all, when the underlying judge model changes (because
the API silently moves you to a new minor version, or you upgrade Sonnet
to Opus, or the prompt changes), your "5.0/5" can become a "3.0/5" with no
change in your application's quality.

Most homemade eval tools just trust the judge. EvalKit doesn't.

## The fix: calibrate against humans

Before you trust the judge in production, you measure how well it agrees
with human labels on a small held-out set. The standard agreement metric
for nominal/ordinal scales is **Cohen's kappa** (or **Fleiss' kappa** for
≥3 raters, or **Krippendorff's alpha** for messy data with missing labels).

EvalKit computes Cohen's κ between the judge's binned score and the mode
of the human labels on the golden set, and *refuses* to deploy the judge if
κ falls below a configurable floor (default `0.7`, substantial agreement).

```python
from evalkit.judges import CalibratedJudge

judge = CalibratedJudge.from_rubric("rubrics/faithfulness.yaml")
report = judge.calibrate("golden.jsonl")

assert report.passes, report.failure_reason
print(f"cohen_kappa = {report.cohen_kappa:.3f}")
```

The rubric YAML carries its own thresholds:

```yaml
calibration:
  kappa_floor: 0.7      # refuse to deploy below this
  min_samples: 30       # need at least this many rows with labels
  bias_threshold: 0.15  # max acceptable bias magnitude
```

## Bias audits

In the same calibration pass, EvalKit runs three audits:

1. **Position bias**, does the judge prefer "A" over "B" when both
   contain identical content, just labelled differently?
2. **Length bias**, does the judge give a longer-but-equivalent answer a
   higher score?
3. **Self-preference bias**, does the judge prefer outputs from the same
   model family it belongs to?

Each audit returns a magnitude in [-1, 1]. If the worst exceeds the
`bias_threshold`, calibration fails the same way kappa < floor would.

## What to do when calibration fails

In rough priority order:

1. **Add anchors to the rubric.** Most calibration failures are rubric
   ambiguity, not judge incompetence. Add a 1, 3, 5 anchor description per
   criterion.
2. **Get more labelled rows.** Below ~30, kappa is statistically noisy.
3. **Switch judges.** Try Sonnet 4.6 instead of Haiku 4.5; calibration will
   tell you if that recovers agreement.
4. **Decompose the rubric.** A single criterion that lumps several judgments
   together is often what's tanking kappa. Split it.

## Reading list

- Cohen, J. (1960). *A coefficient of agreement for nominal scales.* Educ.
  Psychol. Meas. 20: 37–46.
- Krippendorff, K. (2018). *Content Analysis: An Introduction to Its
  Methodology* (4th ed.). Sage.
- Wang et al. (2023). *Large Language Models are not Fair Evaluators.*
  (The paper that made the position-bias problem famous.)
