.PHONY: help install test lint format typecheck ci clean

PY := .venv/bin/python

help:
	@echo "install     Install package + dev deps"
	@echo "test        Run pytest with coverage"
	@echo "lint        ruff check + format check"
	@echo "format      Apply ruff format"
	@echo "typecheck   mypy --strict"
	@echo "ci          lint + typecheck + test"

install:
	uv venv
	uv pip install -e '.[dev,all]'

test:
	$(PY) -m pytest tests -q

lint:
	$(PY) -m ruff check src tests
	$(PY) -m ruff format --check src tests

format:
	$(PY) -m ruff format src tests

typecheck:
	$(PY) -m mypy --strict src

ci: lint typecheck test

clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -exec rm -rf {} + 2>/dev/null || true
	rm -rf dist build *.egg-info
