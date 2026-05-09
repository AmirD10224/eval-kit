# Contributing to EvalKit

Thanks for your interest. EvalKit is a small library trying to be careful
about what it adds, so please read this first.

## TL;DR

```bash
git clone https://github.com/AmirD10224/eval-kit.git
cd eval-kit
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,all]"
pytest
ruff check . && ruff format --check .
mypy
mkdocs serve  # docs at http://127.0.0.1:8000
```

## Ground rules

- **Tests are required.** New code without tests will not be merged. We
  target ≥85% branch coverage and use a deterministic
  [`StubClient`](src/evalkit/llm/stub.py) so contributors don't need an
  Anthropic API key to run the suite.
- **Strict type checking.** Run `mypy` before pushing. New modules ship
  with full annotations; we do not accept `# type: ignore` without a
  comment explaining why.
- **Style is enforced.** `ruff check` and `ruff format` must pass. We use
  Pydantic v2 strict everywhere user data crosses the boundary.
- **Wrap, don't reinvent.** EvalKit is built on top of Ragas, Inspect AI,
  and the Anthropic SDK. If you find yourself reimplementing one of those,
  stop and open an issue first.

## How to propose a change

1. **Open an issue** before starting on anything larger than a one-line
   fix. Describe the use case in user terms ("a team using EvalKit on a
   classification task wants to…").
2. **Fork → branch off `main`.** Branch names like `feat/<short>` or
   `fix/<short>`.
3. **Add tests first.** If you can't write a failing test that captures
   the bug or feature, you don't yet understand the change.
4. **Keep PRs focused.** One logical change per PR. Refactors that touch
   N modules go in their own PR with no behavior changes.
5. **Update `CHANGELOG.md`.** Under `[Unreleased]`, with a one-liner.

## Areas we'd love help on

- More example rubrics under `examples/*/rubrics/` (faithfulness,
  helpfulness, harmlessness, structured-output validity). If we accumulate
  enough, we'll move them into `src/evalkit/judges/rubrics/` and ship them
  with the package, drop into the issue tracker if you'd like to drive
  that conversion.
- More taxonomy categories in `synth/taxonomy.py`.
- Adapters for additional eval backends (Patronus, Arize Phoenix, etc.).
- Real-world example apps under `examples/`.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Don't
be a jerk and report problems to amir10.dhibi@gmail.com.
