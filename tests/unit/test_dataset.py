"""Dataset store + agreement tests."""

from __future__ import annotations

import json

import pytest

from evalkit.dataset.agreement import compute_agreement
from evalkit.dataset.store import GoldenDataset
from evalkit.exceptions import DatasetError


def test_load_validates_each_row(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "g.jsonl"
    p.write_text(
        '{"id": "a", "input": {"q": 1}}\n'
        '{"id": "b", "input": {"q": 2}, "expected": {"a": "yes"}}\n',
    )
    ds = GoldenDataset.load(p)
    assert len(ds) == 2
    assert ds.ids == ["a", "b"]
    assert ds.path == p


def test_load_rejects_invalid_json(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "bad.jsonl"
    p.write_text("not json\n")
    with pytest.raises(DatasetError, match="invalid JSON"):
        GoldenDataset.load(p)


def test_load_rejects_schema_violations(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "bad.jsonl"
    p.write_text('{"id": "a"}\n')  # missing "input"
    with pytest.raises(DatasetError, match="schema error"):
        GoldenDataset.load(p)


def test_load_rejects_duplicate_ids(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "dup.jsonl"
    p.write_text(
        '{"id": "a", "input": {}}\n{"id": "a", "input": {}}\n',
    )
    with pytest.raises(DatasetError, match="duplicate"):
        GoldenDataset.load(p)


def test_load_skips_blank_and_comments(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "g.jsonl"
    p.write_text(
        '\n# comment\n{"id": "a", "input": {}}\n',
    )
    ds = GoldenDataset.load(p)
    assert len(ds) == 1


def test_load_missing_file_raises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(DatasetError, match="not found"):
        GoldenDataset.load(tmp_path / "nope.jsonl")


def test_save_atomic_writes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "out.jsonl"
    ds = GoldenDataset.from_rows([{"id": "x", "input": {}}])
    ds.save(p)
    assert p.exists()
    # No leftover .tmp files in the directory
    assert not any(c.name.startswith(".") for c in tmp_path.iterdir())


def test_save_requires_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    ds = GoldenDataset.from_rows([{"id": "x", "input": {}}])
    with pytest.raises(DatasetError, match="path"):
        ds.save()


def test_add_validates_and_dedupes() -> None:
    ds = GoldenDataset.from_rows([{"id": "a", "input": {}}])
    ds.add({"id": "b", "input": {}})
    with pytest.raises(DatasetError, match="already"):
        ds.add({"id": "a", "input": {}})


def test_validate_file_helper(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "g.jsonl"
    p.write_text('{"id": "a", "input": {}}\n')
    assert GoldenDataset.validate_file(p) == 1


def test_indexing_works() -> None:
    ds = GoldenDataset.from_rows([{"id": "a", "input": {}}])
    assert ds[0].id == "a"


def test_iteration() -> None:
    ds = GoldenDataset.from_rows([{"id": "a", "input": {}}, {"id": "b", "input": {}}])
    assert [r.id for r in ds] == ["a", "b"]


def test_id_no_whitespace_validation() -> None:
    with pytest.raises(DatasetError, match="schema"):
        GoldenDataset.from_rows([{"id": "a b", "input": {}}])


# ---------- agreement -----------------------------------------------------


def test_agreement_two_raters_perfect() -> None:
    ds = GoldenDataset.from_rows(
        [
            {
                "id": f"r-{i}",
                "input": {},
                "labels": [{"score": (i % 5) + 1}, {"score": (i % 5) + 1}],
            }
            for i in range(20)
        ],
    )
    report = compute_agreement(ds)
    assert report.statistic == "cohen"
    assert report.kappa == pytest.approx(1.0)
    assert report.low_agreement_ids == []


def test_agreement_three_raters_uses_fleiss() -> None:
    ds = GoldenDataset.from_rows(
        [
            {
                "id": f"r-{i}",
                "input": {},
                "labels": [{"score": 1}, {"score": 1}, {"score": 1}],
            }
            for i in range(5)
        ],
    )
    report = compute_agreement(ds)
    assert report.statistic == "fleiss"


def test_agreement_skips_under_two_raters() -> None:
    ds = GoldenDataset.from_rows([{"id": "x", "input": {}, "labels": [{"score": 1}]}])
    report = compute_agreement(ds)
    assert report.n_rated_rows == 0


def test_agreement_flags_low_consensus() -> None:
    ds = GoldenDataset.from_rows(
        [{"id": f"r-{i}", "input": {}, "labels": [{"score": 1}, {"score": 5}]} for i in range(15)],
    )
    report = compute_agreement(ds, low_threshold=1.0)
    assert len(report.low_agreement_ids) == 15


def test_agreement_accepts_dict_iterable() -> None:
    rows = [
        {
            "id": f"r-{i}",
            "input": {},
            "labels": [{"score": 1}, {"score": 1}],
        }
        for i in range(15)
    ]
    report = compute_agreement(rows)  # type: ignore[arg-type]
    assert report.statistic == "cohen"


def test_agreement_uneven_rater_counts() -> None:
    rows = [
        {"id": "a", "input": {}, "labels": [{"score": 1}, {"score": 1}, {"score": 1}]},
        {"id": "b", "input": {}, "labels": [{"score": 1}, {"score": 1}]},
    ]
    ds = GoldenDataset.from_rows(rows)
    # Should not raise; uses min count.
    report = compute_agreement(ds)
    assert report.n_raters == 2


def test_save_then_load_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "rt.jsonl"
    ds = GoldenDataset.from_rows(
        [{"id": "a", "input": {"q": "x"}, "expected": {"a": "y"}}],
    )
    ds.save(p)
    loaded = GoldenDataset.load(p)
    assert json.dumps(dict(loaded[0].input)) == json.dumps({"q": "x"})
