# API reference

::: evalkit
    options:
      show_root_heading: false
      members_order: source
      show_if_no_docstring: false

## Top-level imports

```python
from evalkit import (
    Suite, SuiteResult,
    CalibratedJudge, Rubric, CalibrationReport,
    GoldenDataset, RegressionReport,
    SynthGenerator, Taxonomy,
)
```

## Submodules

- :py:mod:`evalkit.judges`. `CalibratedJudge`, `Rubric`, `Judge` protocol,
  bias audits, agreement statistics.
- :py:mod:`evalkit.runner`. `Suite`, `SuiteResult`, `SuiteReport`,
  `MetricResult`, `Sample`.
- :py:mod:`evalkit.dataset`. `GoldenDataset`, `compute_agreement`.
- :py:mod:`evalkit.synth`. `SynthGenerator`, `SynthRequest`, `Taxonomy`.
- :py:mod:`evalkit.diff`. `diff_reports`, `RegressionReport`, `MetricDelta`.
- :py:mod:`evalkit.adapters`. `RagasScorer`, `import_promptfoo_config`,
  Langfuse / Braintrust glue.
- :py:mod:`evalkit.ci`. Markdown + GitHub PR-comment helpers.
- :py:mod:`evalkit.llm`. `AnthropicClient`, `StubClient`.

Each is auto-documented via `mkdocstrings` from the inline docstrings.
