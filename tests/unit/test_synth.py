"""Synth generator tests using a stub LLM that returns fixed lists."""

from __future__ import annotations

import json

import pytest

from evalkit.exceptions import EvalKitError
from evalkit.llm.stub import StubClient
from evalkit.synth.generator import SynthGenerator, SynthRequest, _safe_parse_list
from evalkit.synth.taxonomy import Taxonomy, TaxonomyCategory


def _list_response(n: int = 3) -> str:
    return json.dumps([{"input": {"question": f"q{i}"}} for i in range(n)])


def test_generates_for_all_categories_by_default() -> None:
    client = StubClient(default_response=_list_response(2))
    gen = SynthGenerator(client=client)
    rows = gen.generate(SynthRequest(task="QA", schema={"question": "str"}, count=10))
    assert 1 <= len(rows) <= 10
    cats = {r["metadata"]["taxonomy_category"] for r in rows}
    assert cats <= set(Taxonomy.default().names())


def test_filter_to_specific_categories() -> None:
    client = StubClient(default_response=_list_response(3))
    gen = SynthGenerator(client=client)
    rows = gen.generate(
        SynthRequest(
            task="QA",
            schema={},
            count=3,
            categories=(TaxonomyCategory.JAILBREAKS,),
        ),
    )
    assert all(r["metadata"]["taxonomy_category"] == "jailbreaks" for r in rows)


def test_invalid_count_raises() -> None:
    with pytest.raises(ValueError, match="count"):
        SynthRequest(task="x", schema={}, count=0)


def test_skips_non_dict_items() -> None:
    client = StubClient(default_response=json.dumps([{"input": {}}, "garbage", 42]))
    gen = SynthGenerator(client=client)
    rows = gen.generate(SynthRequest(task="x", schema={}, count=10))
    assert all(isinstance(r, dict) and "id" in r for r in rows)


def test_provenance_attached() -> None:
    client = StubClient(default_response=_list_response(1))
    gen = SynthGenerator(client=client)
    rows = gen.generate(SynthRequest(task="x", schema={}, count=5))
    assert rows
    prov = rows[0]["metadata"]["provenance"]
    assert "prompt_hash" in prov and "model" in prov


def test_safe_parse_list_handles_fences() -> None:
    out = list(_safe_parse_list('```json\n[{"a": 1}]\n```'))
    assert out == [{"a": 1}]


def test_safe_parse_list_returns_empty_on_garbage() -> None:
    assert list(_safe_parse_list("nope")) == []


def test_safe_parse_list_extracts_cases_field() -> None:
    out = list(_safe_parse_list('{"cases": [{"a": 1}]}'))
    assert out == [{"a": 1}]


def test_generator_with_empty_taxonomy_raises() -> None:
    gen = SynthGenerator(client=StubClient(), taxonomy=Taxonomy(categories={}))
    with pytest.raises(EvalKitError):
        gen.generate(SynthRequest(task="x", schema={}, count=1))


def test_taxonomy_unknown_category_raises() -> None:
    with pytest.raises(KeyError, match="unknown"):
        Taxonomy(categories={}).get(TaxonomyCategory.JAILBREAKS)
