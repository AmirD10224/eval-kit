"""Tests for the LLM client + stub."""

from __future__ import annotations

import pytest

from evalkit.llm.client import LLMResponse
from evalkit.llm.stub import StubClient, echo_score_from_prompt


class TestLLMResponse:
    def test_parse_json_plain(self) -> None:
        r = LLMResponse(text='{"a": 1}', model="x", input_tokens=1, output_tokens=1)
        assert r.parse_json() == {"a": 1}

    def test_parse_json_with_fences(self) -> None:
        r = LLMResponse(
            text='```json\n{"a": 1}\n```',
            model="x",
            input_tokens=1,
            output_tokens=1,
        )
        assert r.parse_json() == {"a": 1}

    def test_parse_json_with_plain_fences(self) -> None:
        r = LLMResponse(text="```\n[1, 2]\n```", model="x", input_tokens=1, output_tokens=1)
        assert r.parse_json() == [1, 2]


class TestStubClient:
    def test_default_response_used_when_no_match(self) -> None:
        c = StubClient(default_response='{"x": 1}')
        out = c.complete(system="s", prompt="anything")
        assert out.text == '{"x": 1}'
        assert out.model == "stub-model"

    def test_explicit_responses_take_priority(self) -> None:
        c = StubClient(responses={"hello": "world"}, default_response="other")
        assert c.complete(system="", prompt="hello").text == "world"

    def test_scorer_is_called(self) -> None:
        c = StubClient(scorer=echo_score_from_prompt())
        out = c.complete(system="", prompt="please score=5 on this answer")
        # echo scorer returns {"score": 5, "reasoning": "stub-echo"}
        assert "5" in out.text

    def test_calls_recorded(self) -> None:
        c = StubClient()
        c.complete(system="sys", prompt="p1")
        c.complete(system="sys", prompt="p2")
        assert [call.prompt for call in c.calls] == ["p1", "p2"]
        assert all(call.system == "sys" for call in c.calls)

    def test_custom_model_recorded(self) -> None:
        c = StubClient()
        out = c.complete(system="", prompt="x", model="my-model")
        assert out.model == "my-model"
        assert c.calls[0].model == "my-model"

    def test_noise_jitter_deterministic(self) -> None:
        c1 = StubClient(scorer=echo_score_from_prompt(), noise=2.0, seed=7)
        c2 = StubClient(scorer=echo_score_from_prompt(), noise=2.0, seed=7)
        a = c1.complete(system="", prompt="score=3 here").text
        b = c2.complete(system="", prompt="score=3 here").text
        assert a == b

    def test_echo_score_default(self) -> None:
        scorer = echo_score_from_prompt()
        # When prompt has no score, defaults to 3
        result = scorer("no number here")
        assert result["score"] == 3


class TestAnthropicClientAuth:
    def test_no_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from evalkit.llm.client import AnthropicAuthError, AnthropicClient

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(AnthropicAuthError):
            AnthropicClient()
