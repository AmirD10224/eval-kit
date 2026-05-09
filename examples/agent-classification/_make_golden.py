"""Regenerate examples/agent-classification/golden.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

UTTERANCES = [
    ("I'd like a refund for my last order.", "refund"),
    ("Can you tell me my checking account balance?", "balance"),
    ("Move $200 from savings to checking.", "transfer"),
    ("My card got stolen, I need help.", "support"),
    ("How do I reset my password?", "support"),
    ("Send 500 to my landlord", "transfer"),
    ("What's left on my Visa?", "balance"),
    ("I want my money back, this product is broken.", "refund"),
    ("Tell me a joke.", "unknown"),
    ("Why is the sky blue?", "unknown"),
    ("Refund please.", "refund"),
    ("Wire 1000 EUR to IBAN DE...", "transfer"),
    ("Account balance?", "balance"),
    ("My online banking is broken, please help.", "support"),
    ("balance?", "balance"),
    ("transfer 50 to alice", "transfer"),
    ("RefUnD on order 5712", "refund"),
    ("can someone help me, my account is locked", "support"),
    ("how much do I have", "balance"),
    ("what's the meaning of life", "unknown"),
]


def main() -> None:
    out = Path(__file__).with_name("golden.jsonl")
    with out.open("w", encoding="utf-8") as f:
        for i, (utterance, intent) in enumerate(UTTERANCES):
            row = {
                "id": f"intent-{i:03d}",
                "input": {"utterance": utterance},
                "expected": {"intent": intent},
                "labels": [
                    {"rater": "human-1", "score": 5},
                    {"rater": "human-2", "score": 5 if intent != "unknown" else 4},
                ],
            }
            f.write(json.dumps(row) + "\n")
    print(f"wrote {len(UTTERANCES)} rows → {out}")


if __name__ == "__main__":
    main()
