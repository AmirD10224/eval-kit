"""LLM clients used by judges and synth.

Both backends implement :class:`evalkit.llm.client.LLMClient` so the rest of
the codebase doesn't care which one is in use.
"""

from evalkit.llm.client import AnthropicClient, LLMClient, LLMResponse
from evalkit.llm.stub import StubClient

__all__ = ["AnthropicClient", "LLMClient", "LLMResponse", "StubClient"]
