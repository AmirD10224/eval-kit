# Example: evaluating an intent-classification agent

Smaller, more focused than the QA-RAG example: a single rubric ("did the
agent route the user to the right intent?") plus a regex check on the
output's structured-JSON shape.

## What's here

- `golden.jsonl`. 20 user utterances tagged with the correct intent label
  (`refund`, `balance`, `transfer`, `support`, `unknown`).
- `rubrics/intent.yaml`, single-criterion rubric the judge uses to decide
  whether the agent's output matches the gold intent.
- `suite.yaml`, judge metric + a regex metric that checks the response
  is valid JSON with an `intent` field.

## Run it

```bash
cd examples/agent-classification
evalkit dataset validate golden.jsonl
evalkit run --suite suite.yaml --stub
```
