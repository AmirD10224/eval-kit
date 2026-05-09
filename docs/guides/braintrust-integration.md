# Braintrust

Push EvalKit suite reports to Braintrust as experiments.

## Install

```bash
pip install "evalkit-oss[braintrust]"
export BRAINTRUST_API_KEY=...
```

## Use

```python
from evalkit.adapters.braintrust import push_report
from evalkit.runner.report import SuiteReport

report = SuiteReport.load("current.json")
url = push_report(report, project="my-rag-app")
print(url)   # https://braintrust.dev/...
```

Each metric × sample becomes one Braintrust row, so you get the full per-
sample breakdown in their UI alongside whatever else lives there.

## Why both EvalKit and Braintrust?

If your team already lives in Braintrust, EvalKit is the *upstream*
producer of the data, calibrated judges, regression-aware diff, golden
dataset management, and Braintrust is the dashboard. They compose.
