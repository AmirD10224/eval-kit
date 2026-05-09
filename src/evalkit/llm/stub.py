"""Deterministic stub LLM client used in tests and offline mode.

This is the *only* way the test suite can hit ≥85% coverage without burning
through API credits or requiring contributors to have an Anthropic key. The
stub is fully reproducible: same seed + same prompt → same response.

Two response strategies are supported:

* ``StubClient(responses={...})``, deterministic mapping prompt → text
* ``StubClient(scorer=callable)``, derive a numeric score from the prompt,
  wrap it in the JSON envelope our judges expect

The stub also tracks call history so tests can assert on it.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from evalkit.llm.client import LLMResponse

# ---------------------------------------------------------------------------

ScorerFn = Callable[[str], Mapping[str, Any]]


@dataclass(slots=True)
class StubCall:
    """One recorded call to the stub for test assertions."""

    system: str
    prompt: str
    model: str


@dataclass(slots=True)
class StubClient:
    """Deterministic stand-in for :class:`AnthropicClient`.

    Args:
        responses: Optional mapping from prompt → response text. If a prompt
            isn't in the map, the stub falls back to ``scorer`` (if set), then
            to ``default_response``.
        scorer: Optional callable taking the prompt and returning the
            response *body* (a JSON-serialisable dict, usually a judge
            score). The stub wraps it in a JSON string with optional noise.
        default_response: Returned when neither ``responses`` nor ``scorer``
            applies. Defaults to a benign judge envelope.
        noise: Standard deviation of pseudo-random integer noise added to
            scorer outputs (deterministic from prompt hash). 0.0 = no noise.
        seed: Seeds the deterministic noise.
    """

    responses: Mapping[str, str] = field(default_factory=dict)
    scorer: ScorerFn | None = None
    default_response: str = '{"score": 3, "reasoning": "stub default"}'
    noise: float = 0.0
    seed: int = 0
    model_name: str = "stub-model"

    calls: list[StubCall] = field(default_factory=list)

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1024,  # noqa: ARG002
        temperature: float = 0.0,  # noqa: ARG002
        seed: int | None = None,  # noqa: ARG002
    ) -> LLMResponse:
        chosen_model = model or self.model_name
        self.calls.append(StubCall(system=system, prompt=prompt, model=chosen_model))

        if prompt in self.responses:
            text = self.responses[prompt]
        elif self.scorer is not None:
            text = self._render_scorer(prompt)
        else:
            text = self.default_response

        return LLMResponse(
            text=text,
            model=chosen_model,
            input_tokens=len(prompt) // 4,
            output_tokens=len(text) // 4,
        )

    # ------------------------------------------------------------------

    def _render_scorer(self, prompt: str) -> str:
        assert self.scorer is not None
        body = dict(self.scorer(prompt))
        if self.noise > 0 and "score" in body and isinstance(body["score"], int | float):
            jitter = self._deterministic_jitter(prompt)
            body["score"] = max(1, round(body["score"] + jitter * self.noise))
        return json.dumps(body)

    def _deterministic_jitter(self, prompt: str) -> float:
        """Return a value in roughly [-1, 1] that is stable per prompt.

        We hash ``(seed, prompt)`` and map to a float, way faster than
        spinning up ``random.Random`` and avoids any hidden state.
        """
        digest = hashlib.sha256(f"{self.seed}:{prompt}".encode()).digest()
        # Take 8 bytes, convert to int, normalise to [-1, 1].
        n = int.from_bytes(digest[:8], "big") / 2**64
        return (n * 2.0) - 1.0


def echo_score_from_prompt(pattern: str = r"score=(\d+)") -> ScorerFn:
    """Build a scorer that picks an integer score out of the prompt.

    Useful for tests where the desired score is encoded directly in the
    prompt. Falls back to 3 (mid-scale) if nothing matches.
    """
    rx = re.compile(pattern)

    def _scorer(prompt: str) -> Mapping[str, Any]:
        m = rx.search(prompt)
        score = int(m.group(1)) if m else 3
        return {"score": score, "reasoning": "stub-echo"}

    return _scorer
