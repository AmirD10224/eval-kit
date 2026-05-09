"""One-off script to (re-)generate examples/qa-rag/golden.jsonl.

This file is committed; the script is here for reproducibility.
"""

from __future__ import annotations

import json
from pathlib import Path

_FACTS = [
    ("What's the capital of France?", ["Paris is the capital of France."], "Paris"),
    (
        "When did the Apollo 11 land on the moon?",
        ["Apollo 11 landed on the moon on July 20, 1969."],
        "July 20, 1969",
    ),
    (
        "Who wrote 'Pride and Prejudice'?",
        ["Pride and Prejudice was written by Jane Austen, published in 1813."],
        "Jane Austen",
    ),
    (
        "What is the boiling point of water at sea level?",
        ["At sea level, water boils at 100 degrees Celsius (212 Fahrenheit)."],
        "100 degrees Celsius",
    ),
    (
        "What is the speed of light in a vacuum?",
        ["The speed of light in a vacuum is approximately 299,792 km/s."],
        "299,792 km/s",
    ),
    (
        "Who painted the Mona Lisa?",
        ["The Mona Lisa was painted by Leonardo da Vinci."],
        "Leonardo da Vinci",
    ),
    (
        "What's the tallest mountain on Earth?",
        ["Mount Everest, at 8,848.86 m, is the tallest mountain above sea level."],
        "Mount Everest",
    ),
    (
        "Which gas do plants absorb during photosynthesis?",
        ["Plants absorb carbon dioxide (CO2) from the atmosphere during photosynthesis."],
        "carbon dioxide",
    ),
    (
        "Who is credited with inventing the telephone?",
        ["Alexander Graham Bell is credited with inventing the practical telephone in 1876."],
        "Alexander Graham Bell",
    ),
    (
        "What is the Pythagorean theorem?",
        ["For a right triangle with legs a, b and hypotenuse c: a^2 + b^2 = c^2."],
        "a^2 + b^2 = c^2",
    ),
    (
        "What's the chemical symbol for gold?",
        ["Gold has the chemical symbol Au, from the Latin 'aurum'."],
        "Au",
    ),
    (
        "Who developed the theory of general relativity?",
        ["Albert Einstein developed the theory of general relativity, published in 1915."],
        "Albert Einstein",
    ),
    (
        "How many continents are there?",
        ["There are seven continents: Africa, Antarctica, Asia, Australia, Europe, North America, South America."],
        "seven",
    ),
    (
        "What language is spoken in Brazil?",
        ["Portuguese is the official and most widely spoken language in Brazil."],
        "Portuguese",
    ),
    (
        "What is the largest planet in our solar system?",
        ["Jupiter is the largest planet in the solar system, larger than all the others combined."],
        "Jupiter",
    ),
    (
        "What does DNA stand for?",
        ["DNA stands for deoxyribonucleic acid."],
        "deoxyribonucleic acid",
    ),
    (
        "Who is the current CEO of Anthropic?",
        [],  # intentionally no context, system should say "I don't know"
        "I don't know.",
    ),
    (
        "What's the population of Mars?",
        [],
        "I don't know.",
    ),
    (
        "Tell me a stock tip for next week.",
        [],
        "I don't know.",
    ),
    (
        "Which year did France win its first FIFA World Cup?",
        ["France won its first FIFA World Cup in 1998, hosting the tournament."],
        "1998",
    ),
    (
        "What's the smallest prime number?",
        ["The smallest prime number is 2; it's also the only even prime."],
        "2",
    ),
    (
        "Who composed the Fifth Symphony often associated with 'fate knocking'?",
        ["Ludwig van Beethoven composed his Fifth Symphony, premiered in 1808."],
        "Ludwig van Beethoven",
    ),
    (
        "What is the currency of Japan?",
        ["The Japanese yen is the official currency of Japan."],
        "yen",
    ),
    (
        "What's the chemical formula of water?",
        ["Water has the chemical formula H2O."],
        "H2O",
    ),
    (
        "Who wrote 'Hamlet'?",
        ["William Shakespeare wrote Hamlet, around 1600."],
        "William Shakespeare",
    ),
    (
        "What is the longest river in the world?",
        ["The Nile is generally considered the longest river in the world at about 6,650 km."],
        "Nile",
    ),
    (
        "What does HTTP stand for?",
        ["HTTP stands for Hypertext Transfer Protocol."],
        "Hypertext Transfer Protocol",
    ),
    (
        "Who painted the ceiling of the Sistine Chapel?",
        ["Michelangelo painted the ceiling of the Sistine Chapel between 1508 and 1512."],
        "Michelangelo",
    ),
    (
        "What planet is known as the Red Planet?",
        ["Mars is often called the Red Planet because of its reddish surface."],
        "Mars",
    ),
    (
        "How many keys are on a standard piano?",
        ["A standard piano has 88 keys: 52 white and 36 black."],
        "88",
    ),
]


def main() -> None:
    out = Path(__file__).with_name("golden.jsonl")
    with out.open("w", encoding="utf-8") as f:
        for i, (question, contexts, answer) in enumerate(_FACTS):
            row = {
                "id": f"qa-{i:03d}",
                "input": {"question": question, "contexts": contexts},
                "expected": {"answer": answer},
                "metadata": {"closed_book": not contexts},
                # Two synthetic raters: both gave high marks since these are
                # well-defined factual questions. In real life you'd label
                # them yourself or via a labeling tool.
                "labels": [
                    {"rater": "rater-1", "score": 5 if contexts else 4},
                    {"rater": "rater-2", "score": 5 if contexts else 4},
                ],
            }
            f.write(json.dumps(row))
            f.write("\n")
    print(f"wrote {len(_FACTS)} rows → {out}")


if __name__ == "__main__":
    main()
