"""Per-row provenance metadata for synth output.

Every synthetically generated row carries a :class:`Provenance` block in its
``metadata`` so downstream consumers know which model produced it, under what
taxonomy category, with what prompt hash. This is what makes synth output
auditable instead of "magic" data.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Provenance:
    """A signed receipt for one synthetically generated row."""

    generator: str  # e.g. "evalkit.synth.v1"
    model: str
    taxonomy_category: str
    prompt_hash: str
    seed: int
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @classmethod
    def build(
        cls,
        *,
        generator: str = "evalkit.synth.v1",
        model: str,
        category: str,
        prompt: str,
        seed: int,
    ) -> Provenance:
        return cls(
            generator=generator,
            model=model,
            taxonomy_category=category,
            prompt_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
            seed=seed,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
