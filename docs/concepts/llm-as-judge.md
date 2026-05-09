# LLM-as-judge

A judge is anything that takes `(input, output[, expected])` and returns a
:class:`JudgeOutput`, a numeric score in [0, 1], per-criterion ints, and
an optional reasoning string.

## The default: CalibratedJudge

```python
from evalkit.judges import CalibratedJudge

judge = CalibratedJudge.from_rubric("rubrics/faithfulness.yaml")
verdict = judge.score(
    input_data={"question": "...", "contexts": [...]},
    output_data={"answer": "..."},
)
print(verdict.score, verdict.criterion_scores)
```

This is what you should use 95% of the time. It loads a YAML rubric, runs
[calibration](calibration.md) against your golden set, audits for bias, and
refuses to deploy when agreement is too low.

## Custom judges

Anything implementing this protocol works:

```python
from evalkit.judges.base import Judge, JudgeOutput

class MyHeuristicJudge:
    def score(self, *, input_data, output_data, expected=None):
        score = 1.0 if "answer" in output_data else 0.0
        return JudgeOutput(
            score=score,
            criterion_scores={"has_answer": int(score * 5)},
            reasoning="checks if 'answer' key exists",
            raw_response="",
        )

# Plug into the runner via the suite's `kind: custom` mechanism.
suite.register_scorer("my_heuristic", lambda i, o, e: MyHeuristicJudge().score(
    input_data=i, output_data=o, expected=e
).score)
```

## Offline mode

Tests, demos, or offline development don't require an API key, pass a
:class:`StubClient` to the judge:

```python
from evalkit.llm.stub import StubClient
from evalkit.judges import CalibratedJudge

stub = StubClient(default_response='{"grounded": 5, "no_invention": 5}')
judge = CalibratedJudge.from_rubric("rubrics/faithfulness.yaml", client=stub)
```

The CLI offers `--stub` on every verb that hits the LLM.

## Picking a judge model

| Model            | When to use                                         |
| ---------------- | --------------------------------------------------- |
| Claude Haiku 4.5 | default, fast, cheap, calibrates well with anchors |
| Claude Sonnet 4.6 | when Haiku can't reach κ ≥ 0.7 even with anchors   |
| Claude Opus 4.7  | high-stakes evals (safety-relevant rubrics)         |

Set per-suite via `judge_model:` in the suite YAML, or per-call in code.
