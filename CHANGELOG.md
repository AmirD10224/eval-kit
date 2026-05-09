# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-05-06

### Added

- Initial public release.
- **Synthetic data generation** (`evalkit synth generate`): taxonomy-based
  generator covering edge cases, jailbreaks, multi-turn, PII probes, and
  distribution shift, with provenance tracking.
- **Golden dataset management** (`evalkit dataset add|validate`): JSONL store
  with schema validation, multi-rater Cohen's / Fleiss' kappa, and
  git-based versioning.
- **Calibrated LLM-as-judge** (`evalkit.judges.CalibratedJudge`): YAML rubric
  loader, calibration against the golden set, position / length /
  self-preference bias detection, and a deploy gate at kappa ≥ 0.7.
- **Eval runner** (`evalkit run`): parallel suite execution with Rich
  terminal output and JSON report.
- **Regression detection** (`evalkit diff`): metric deltas with configurable
  thresholds and a structured CI exit code.
- **GitHub Action** (root `action.yml`): runs an eval suite on a PR, posts
  a Markdown comment showing metric deltas, and fails the check on
  regressions beyond a threshold.
- **Adapters**: Ragas (built-in metrics), Inspect AI (task/solver/scorer
  bridge), promptfoo (config import), Langfuse (trace pull, optional),
  Braintrust (alt backend, optional).
- **Examples**: `qa-rag`, `agent-classification`, `regression-demo`
  (the demo produces `docs/screenshots/auto-reject.png`).
- **Documentation**: mkdocs-material site published to GitHub Pages.

[Unreleased]: https://github.com/AmirD10224/eval-kit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AmirD10224/eval-kit/releases/tag/v0.1.0
