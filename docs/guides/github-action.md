# GitHub Action

The drop-in CI integration. One workflow file, two minutes of setup.

## Minimal setup

`.github/workflows/eval.yml`:

```yaml
name: eval
on: [pull_request]
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }   # we need history to resolve the baseline ref
      - uses: AmirD10224/eval-kit@v0.1.0
        with:
          suite: examples/qa-rag/suite.yaml
          baseline: main
          fail-on-regression: 5
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Inputs

| Input                | Default                  | Notes                                    |
| -------------------- | ------------------------ | ---------------------------------------- |
| `suite`              | required                 | Path to the suite YAML                   |
| `baseline`           | `main`                   | Git ref **or** path to a baseline JSON   |
| `predictions`        | (none)                   | Optional predictions JSONL               |
| `output`             | `evalkit-report.json`    | Where to save the current run            |
| `fail-on-regression` | `5`                      | Threshold in percentage points           |
| `comment`            | `true`                   | Whether to post a PR comment             |
| `python-version`     | `3.12`                   | Python version on the runner             |

## Outputs

| Output            | Notes                                            |
| ----------------- | ------------------------------------------------ |
| `has_regressions` | `true` if the diff exceeded the threshold       |
| `report_path`     | Path to the JSON report (also uploaded as artifact) |

## Permissions

The action posts comments via `${{ github.token }}` if you don't pass a
`GITHUB_TOKEN` env var. Make sure your workflow has at least:

```yaml
permissions:
  contents: read
  pull-requests: write
```

## Caching the baseline

Re-running the suite at the baseline ref every PR is the slow path. If
your team prefers to pre-compute baselines on every merge to `main`, save
the JSON as a release asset and pass `baseline:` as a path:

```yaml
- uses: AmirD10224/eval-kit@v0.1.0
  with:
    suite: suites/main.yaml
    baseline: ./.evalkit/main-baseline.json
    fail-on-regression: 5
```

## Local debugging

Reproduce locally with the same machinery:

```bash
evalkit run --suite suites/main.yaml --output current.json
git stash    # or check out main
evalkit run --suite suites/main.yaml --output baseline.json
git stash pop
evalkit diff --baseline baseline.json --current current.json --threshold 5
```
