"""Toy RAG QA system used by the regression-demo / real-PR walkthrough.

Reads ``golden.jsonl``, returns a naive context-overlap "answer" per row.
This is the script you'd modify in a PR to introduce a regression EvalKit
catches.
"""

from __future__ import annotations

import json
from pathlib import Path


def _toy_answer(question: str, contexts: list[str]) -> str:
    if not contexts:
        return "I don't know."
    q_tokens = set(question.lower().split())
    return max(contexts, key=lambda c: len(q_tokens & set(c.lower().split())))


def main(golden: Path) -> int:
    for line in golden.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        row = json.loads(line)
        contexts = row["input"].get("contexts", [])
        answer = _toy_answer(row["input"]["question"], contexts)
        print(json.dumps({"id": row["id"], "output": {"answer": answer}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(__file__).with_name("golden.jsonl")))
