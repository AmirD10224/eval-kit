"""Toy RAG QA system.

Reads `golden.jsonl`, "retrieves" the context that was already attached to
each row (yes, this is a stand-in for a real retriever), generates an answer
by string-formatting the context, and prints predictions as JSONL.

Real RAG systems would: embed the question, hit a vector store, run an LLM.
The point of the example is to show the EvalKit plumbing, not the retriever.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _toy_answer(question: str, contexts: list[str]) -> str:
    if not contexts:
        return "I don't know."
    # Naive: return the most question-overlapping context as the "answer".
    q_tokens = set(question.lower().split())
    best = max(
        contexts,
        key=lambda c: len(q_tokens & set(c.lower().split())),
    )
    return best


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
