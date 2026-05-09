"""Synthetic test-case generator.

Drives an LLM (or stub) over the configured taxonomy to produce a diverse
set of adversarial inputs. Output is JSONL-friendly :class:`DatasetRow`-like
dicts ready for ``evalkit dataset add``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from evalkit.exceptions import EvalKitError
from evalkit.llm.client import DEFAULT_JUDGE_MODEL, LLMClient
from evalkit.synth.provenance import Provenance
from evalkit.synth.taxonomy import Taxonomy, TaxonomyCategory

_SYSTEM = (
    "You are an adversarial test-case generator for an LLM application. "
    "Produce realistic, *diverse* inputs that probe weaknesses in the system. "
    "Output STRICT JSON ONLY: a list of objects with the keys "
    '"input" (object matching the task schema), "metadata" (object), and '
    'optionally "expected" (object). No prose, no markdown.'
)

_USER_TMPL = (
    "TASK: {task}\n"
    "TASK SCHEMA (the keys 'input' must contain): {schema}\n"
    "CATEGORY: {category}\n"
    "CATEGORY DESCRIPTION: {category_desc}\n"
    "CATEGORY INSTRUCTION: {instruction}\n"
    "SEED EXAMPLES (do not copy verbatim, generate new ones):\n{seeds}\n\n"
    "Generate exactly {count} new cases for this category."
)


@dataclass(frozen=True, slots=True)
class SynthRequest:
    """One request to the generator."""

    task: str
    schema: dict[str, Any]
    count: int
    categories: tuple[TaxonomyCategory, ...] | None = None  # None ⇒ all
    seed: int = 42
    model: str = DEFAULT_JUDGE_MODEL

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("count must be ≥ 1")


@dataclass
class SynthGenerator:
    """Generate adversarial test rows over a taxonomy.

    Args:
        client: any :class:`LLMClient`. In tests, pass :class:`StubClient`
            with a deterministic response map.
        taxonomy: the taxonomy to draw categories from. Defaults to the
            built-in :meth:`Taxonomy.default`.
    """

    client: LLMClient
    taxonomy: Taxonomy = field(default_factory=Taxonomy.default)

    def generate(self, request: SynthRequest) -> list[dict[str, Any]]:
        """Run the request, return validated row dicts ready for the dataset store."""
        cats = (
            list(request.categories)
            if request.categories is not None
            else list(self.taxonomy.categories)
        )
        if not cats:
            raise EvalKitError("taxonomy has no categories")

        per_category = max(1, request.count // len(cats))
        leftover = request.count - per_category * len(cats)

        rows: list[dict[str, Any]] = []
        next_id = 0

        for i, cat in enumerate(cats):
            spec = self.taxonomy.get(cat)
            n = per_category + (1 if i < leftover else 0)
            prompt = _USER_TMPL.format(
                task=request.task,
                schema=json.dumps(request.schema),
                category=spec.name.value,
                category_desc=spec.description,
                instruction=spec.instruction,
                seeds="\n".join(f"- {ex}" for ex in spec.seed_examples),
                count=n,
            )
            response = self.client.complete(
                system=_SYSTEM,
                prompt=prompt,
                model=request.model,
                temperature=0.7,
                max_tokens=2048,
                seed=request.seed + i,
            )
            generated = _safe_parse_list(response.text)
            for j, item in enumerate(generated):
                if not isinstance(item, dict):
                    continue
                row_id = f"synth-{spec.name.value}-{request.seed:04d}-{next_id:04d}"
                next_id += 1
                provenance = Provenance.build(
                    model=response.model,
                    category=spec.name.value,
                    prompt=prompt,
                    seed=request.seed + i,
                )
                row: dict[str, Any] = {
                    "id": row_id,
                    "input": item.get("input", item),
                    "metadata": {
                        **(item.get("metadata") or {}),
                        "provenance": provenance.to_dict(),
                        "taxonomy_category": spec.name.value,
                        "synth_index": j,
                    },
                }
                if "expected" in item:
                    row["expected"] = item["expected"]
                rows.append(row)
        return rows[: request.count]


def _safe_parse_list(text: str) -> Iterable[Any]:
    """Best-effort JSON-list parse. Returns ``[]`` on failure rather than raising -
    synth is allowed to skip bad LLM outputs, just not silently corrupt good ones.
    """
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1 :]
        if text.endswith("```"):
            text = text[:-3].rstrip()
        if text.startswith("json"):
            text = text[len("json") :].lstrip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return list(data)
    if isinstance(data, dict):
        cases = data.get("cases")
        if isinstance(cases, list):
            return list(cases)
    return []
