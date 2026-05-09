"""Rubric loader / renderer tests."""

from __future__ import annotations

import json

import pytest

from evalkit.exceptions import ConfigError
from evalkit.judges.rubric import Rubric


def test_load_from_text(rubric_yaml: str) -> None:
    r = Rubric.from_text(rubric_yaml)
    assert r.name == "faithfulness"
    assert r.criterion_names == ["grounded", "no_invention"]


def test_load_from_yaml_path(tmp_path, rubric_yaml: str) -> None:
    p = tmp_path / "r.yaml"
    p.write_text(rubric_yaml)
    r = Rubric.from_yaml(p)
    assert r.name == "faithfulness"


def test_render_system_includes_criteria(rubric: Rubric) -> None:
    s = rubric.render_system()
    assert "grounded" in s
    assert "no_invention" in s
    assert "JSON" in s.upper()


def test_render_user_serialises_blocks(rubric: Rubric) -> None:
    msg = rubric.render_user(
        input_data={"q": "hi"},
        output_data={"a": "yes"},
        expected={"a": "yep"},
    )
    assert '"q": "hi"' in msg
    assert '"a": "yes"' in msg


def test_aggregate_normalises_to_unit_interval(rubric: Rubric) -> None:
    s = rubric.aggregate({"grounded": 5, "no_invention": 5})
    assert s == pytest.approx(1.0)
    s0 = rubric.aggregate({"grounded": 1, "no_invention": 1})
    assert s0 == pytest.approx(0.0)
    sm = rubric.aggregate({"grounded": 3, "no_invention": 3})
    assert sm == pytest.approx(0.5)


def test_aggregate_all_zero_weights_now_rejected() -> None:
    """A rubric where every criterion has weight=0 collapses aggregate to 0
    silently, we reject at validation time so users notice the bug.
    """
    yaml_str = """\
name: zero
description: rubric with zero-weighted criterion
criteria:
  - name: only
    description: only
    scale: 5
    weight: 0
"""
    with pytest.raises(ConfigError, match="non-zero weight"):
        Rubric.from_text(yaml_str)


def test_aggregate_with_mixed_weights_partial_zero_ok() -> None:
    """One zero-weight criterion in a multi-criterion rubric is fine."""
    yaml_str = """\
name: mixed
description: rubric with one zero-weighted criterion
criteria:
  - name: a
    description: counted
    scale: 5
    weight: 1.0
  - name: b
    description: ignored (weight 0)
    scale: 5
    weight: 0.0
"""
    r = Rubric.from_text(yaml_str)
    # b's score doesn't influence the aggregate.
    assert r.aggregate({"a": 5, "b": 1}) == pytest.approx(1.0)


def test_invalid_yaml_raises() -> None:
    with pytest.raises(ConfigError, match="invalid YAML"):
        Rubric.from_text(": : :")


def test_non_mapping_yaml_raises() -> None:
    with pytest.raises(ConfigError, match="mapping"):
        Rubric.from_text("- a\n- b\n")


def test_validation_error_raises() -> None:
    with pytest.raises(ConfigError, match="validation failed"):
        Rubric.from_text("name: x\n")  # missing description+criteria


def test_anchors_appear_in_system_prompt() -> None:
    yaml_str = """\
name: anchored
description: rubric with anchors
criteria:
  - name: only
    description: only
    scale: 3
    anchors:
      1: bad
      3: great
"""
    s = Rubric.from_text(yaml_str).render_system()
    assert "anchors" in s
    assert "bad" in s and "great" in s


def test_render_user_handles_objects() -> None:
    """Non-JSON-serialisable defaults shouldn't blow up, we use ``default=str``."""
    yaml_str = """\
name: x
description: y
criteria:
  - name: a
    description: a
    scale: 5
"""
    r = Rubric.from_text(yaml_str)
    msg = r.render_user(input_data={"k": object()}, output_data={"k": object()})
    json.loads(json.dumps({"raw": msg}))  # smoke: shouldn't raise
