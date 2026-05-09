# Langfuse

EvalKit pulls Langfuse traces and runs metrics on production data.

## Install

```bash
pip install "evalkit-oss[langfuse]"
```

Set your Langfuse credentials in env vars:

```bash
export LANGFUSE_PUBLIC_KEY=...
export LANGFUSE_SECRET_KEY=...
export LANGFUSE_HOST=https://cloud.langfuse.com   # or your self-hosted URL
```

## Pulling traces

```python
from datetime import UTC, datetime, timedelta
from evalkit.adapters.langfuse import pull_traces

since = datetime.now(UTC) - timedelta(hours=24)
rows = pull_traces(since=since, name="rag.qa", limit=200)
```

`rows` is a list of EvalKit-shaped dicts (`id`, `input`, `output`,
`metadata.langfuse.{trace_id,session_id,user_id}`) ready to write into a
JSONL and feed to `evalkit run`.

## Pushing scores back

```python
from evalkit.adapters.langfuse import push_score

push_score(trace_id="...", name="faithfulness", value=0.85,
           comment="evalkit calibrated judge")
```

This appears as a Langfuse score on the trace, so your team's existing
Langfuse dashboards pick it up automatically.

## Pattern: nightly production eval

```python
# In a scheduled job:
rows = pull_traces(since=yesterday, limit=500)
write_jsonl("prod-traces.jsonl", rows)
suite = Suite.from_yaml("suites/prod.yaml")
result = suite.run(predictions="prod-traces.jsonl")
result.save(f"reports/{today}.json")
for metric in result.report.metrics:
    for sample in metric.samples:
        push_score(trace_id=sample.row_id, name=metric.name, value=sample.score)
```
