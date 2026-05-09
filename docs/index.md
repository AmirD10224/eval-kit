---
title: EvalKit
---

# EvalKit

> **Production-grade eval harness for LLM apps.** Synthetic data, calibrated
> LLM-as-judge, regression detection, and a GitHub Action that auto-rejects
> regressing PRs, all in one library.

```bash
pip install evalkit-oss
```

## What is this?

EvalKit is what you wish you had after the third "the prompt change worked
on my five examples but broke production" moment. It wraps three already-
excellent libraries. [Ragas](https://github.com/explodinggradients/ragas),
[Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai), and
[promptfoo](https://github.com/promptfoo/promptfoo), into a single workflow
your team can drop into CI in an afternoon.

## The pitch in one screenshot

When a PR drops a tracked metric beyond the configured threshold, the
EvalKit GitHub Action posts a comment showing the diff and fails the check:

![auto-reject](screenshots/auto-reject.png)

That's the difference between "we improved the prompt" and "we improved the
prompt and have evidence."

## Where to next

<div class="grid cards" markdown>

- :material-rocket-launch: **[Quickstart](quickstart.md)**, install + first
  eval in 10 minutes.
- :material-scale-balance: **[Calibration](concepts/calibration.md)**, the
  thing 99% of homemade eval tools skip.
- :material-format-list-bulleted-square: **[Synthetic data](concepts/synthetic-data.md)** -
  the taxonomy approach.
- :material-github: **[GitHub Action](guides/github-action.md)**, drop-in
  CI auto-reject.

</div>

## Why another eval tool?

| Feature                                  | EvalKit | Hand-rolled scripts | Ragas alone | promptfoo alone |
| ---------------------------------------- | :-----: | :-----------------: | :---------: | :-------------: |
| Calibrated LLM-judge (Cohen's κ ≥ 0.7)   |   ✅    |          ✗          |      ✗      |        ✗        |
| Position / length / self-pref bias tests |   ✅    |          ✗          |      ✗      |        ✗        |
| Multi-rater agreement (κ, Fleiss')       |   ✅    |          ✗          |      ✗      |        ✗        |
| Synthetic adversarial data (taxonomy)    |   ✅    |       partial       |      ✗      |     partial     |
| Regression detection in CI               |   ✅    |       partial       |      ✗      |     partial     |
| GitHub Action that blocks the PR         |   ✅    |          ✗          |      ✗      |        ✗        |
| Ragas + Inspect + promptfoo wrapper      |   ✅    |          ✗          |     own     |       own       |

## License

[MIT](https://github.com/AmirD10224/eval-kit/blob/main/LICENSE).
