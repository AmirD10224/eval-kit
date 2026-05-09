# Custom judges

EvalKit's built-in :class:`CalibratedJudge` uses Claude Haiku 4.5 by default,
but anything satisfying the :class:`evalkit.judges.base.Judge` protocol
plugs in.

## Replace just the LLM client

If you want to keep `CalibratedJudge` but swap the underlying LLM (a
self-hosted model, OpenAI, etc.), implement
:class:`evalkit.llm.client.LLMClient`:

```python
from dataclasses import dataclass
from evalkit.llm.client import LLMResponse

class OpenAIClient:
    def __init__(self, api_key: str, model: str = "gpt-4.1-mini") -> None:
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def complete(self, *, system, prompt, model=None, max_tokens=1024,
                 temperature=0.0, seed=None):
        resp = self._client.chat.completions.create(
            model=model or self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        msg = resp.choices[0].message
        return LLMResponse(
            text=msg.content or "",
            model=resp.model,
            input_tokens=resp.usage.prompt_tokens,
            output_tokens=resp.usage.completion_tokens,
        )

# Use it:
from evalkit.judges import CalibratedJudge
judge = CalibratedJudge.from_rubric(
    "rubrics/faithfulness.yaml",
    client=OpenAIClient(api_key=...),
)
```

## Fully custom judge

For non-LLM judges (heuristic, fine-tuned classifier, hybrid), implement
the full :class:`Judge` protocol:

```python
from evalkit.judges.base import Judge, JudgeOutput

class RegexHeuristicJudge:
    def __init__(self, must_contain: list[str]) -> None:
        self.must_contain = must_contain

    def score(self, *, input_data, output_data, expected=None):
        text = str(output_data.get("answer", ""))
        hits = sum(1 for term in self.must_contain if term in text)
        score = hits / len(self.must_contain) if self.must_contain else 0.0
        return JudgeOutput(
            score=score,
            criterion_scores={"keyword_recall": int(score * 5) + 1},
            reasoning=f"matched {hits}/{len(self.must_contain)} terms",
            raw_response="",
        )

# Plug into a suite via kind: custom + register_scorer:
suite.register_scorer(
    "keyword_recall",
    lambda i, o, e: RegexHeuristicJudge(["Paris", "France"]).score(
        input_data=i, output_data=o, expected=e
    ).score,
)
```
