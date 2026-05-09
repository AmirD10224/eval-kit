"""LLM client protocol and the production Anthropic implementation.

The protocol exists so calibration / runner code can take *any* client (real
Claude, a local stub, a mock, a different vendor) without conditionals.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from evalkit.exceptions import EvalKitError

if TYPE_CHECKING:  # pragma: no cover
    from anthropic import Anthropic


DEFAULT_JUDGE_MODEL = "claude-haiku-4-5-20251001"


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Minimal response shape returned by every backend."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int

    def parse_json(self) -> object:
        """Parse the response as JSON, stripping common markdown fences."""
        text = self.text.strip()
        if text.startswith("```"):
            # ```json\n{...}\n```  →  {...}
            text = text.split("\n", 1)[1] if "\n" in text else text
            if text.endswith("```"):
                text = text[: -len("```")].rstrip()
            text = text.removeprefix("json").strip()
        return json.loads(text)


@runtime_checkable
class LLMClient(Protocol):
    """Anything that can take a prompt and return an :class:`LLMResponse`."""

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        seed: int | None = None,
    ) -> LLMResponse:
        """Run a single completion. Implementations should be stateless."""
        ...


class AnthropicAuthError(EvalKitError):
    """Raised when ``ANTHROPIC_API_KEY`` is not set and a real call is attempted."""


class AnthropicClient:
    """Production client around the Anthropic SDK with retries.

    The default model is Claude Haiku 4.5, fast and cheap enough for
    judge work, with rubric calibration to handle the quality gap vs. Sonnet.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        default_model: str = DEFAULT_JUDGE_MODEL,
        max_retries: int = 3,
    ) -> None:
        resolved = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved:
            raise AnthropicAuthError(
                "ANTHROPIC_API_KEY is not set. Either export it or pass api_key=...",
            )
        # Imported lazily so test environments without the SDK installed don't choke.
        from anthropic import Anthropic  # noqa: PLC0415

        self._client: Anthropic = Anthropic(api_key=resolved, max_retries=0)
        self._default_model = default_model
        self._max_retries = max_retries

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        seed: int | None = None,  # noqa: ARG002 (Anthropic API does not yet accept seed)
    ) -> LLMResponse:
        model_name = model or self._default_model
        return self._call(
            system=system,
            prompt=prompt,
            model_name=model_name,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def _call(
        self,
        *,
        system: str,
        prompt: str,
        model_name: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        # Retry only on transient classes (network blips, 5xx, rate limits).
        # 4xx user errors (auth, bad-request) are deterministic, retrying
        # 3 times burns money and time without changing the outcome. We
        # apply tenacity programmatically so ``self._max_retries`` (passed
        # to __init__) actually controls behaviour.
        retryable = _retryable_exception_classes()
        retrying = Retrying(
            stop=stop_after_attempt(max(1, self._max_retries)),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(retryable),
            reraise=True,
        )
        for attempt in retrying:
            with attempt:
                message = self._client.messages.create(
                    model=model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                )
        text_parts: list[str] = []
        for block in message.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                text_parts.append(text)
        return LLMResponse(
            text="".join(text_parts),
            model=message.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )


def _retryable_exception_classes() -> tuple[type[BaseException], ...]:
    """Build the tenacity ``retry_if_exception_type`` argument lazily.

    Done lazily so importing :mod:`evalkit.llm.client` doesn't pull the
    Anthropic SDK at import time.
    """
    classes: list[type[BaseException]] = []
    try:
        import anthropic  # noqa: PLC0415

        for name in (
            "APIConnectionError",
            "APITimeoutError",
            "RateLimitError",
            "InternalServerError",
            "APIStatusError",
        ):
            cls = getattr(anthropic, name, None)
            if isinstance(cls, type) and issubclass(cls, BaseException):
                classes.append(cls)
    except ImportError:
        pass
    try:
        import httpx  # noqa: PLC0415

        classes.append(httpx.HTTPError)
    except ImportError:
        pass
    if not classes:
        # Fall back to the broad superclass so we never silently no-op retry,
        # but importing without anthropic+httpx is unsupported in production.
        classes.append(Exception)
    return tuple(classes)
