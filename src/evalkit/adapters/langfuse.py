"""Langfuse adapter, pull production traces and feed them through EvalKit.

The integration is intentionally one-directional: we *consume* Langfuse
traces, run our metrics on them, and (optionally) write the scores back as
trace observations. We don't replace Langfuse's own scoring features; we
add EvalKit's regression-aware ones on top.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from evalkit.exceptions import AdapterError


def pull_traces(
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    name: str | None = None,
    user_id: str | None = None,
    public_key: str | None = None,
    secret_key: str | None = None,
    host: str | None = None,
) -> list[dict[str, Any]]:
    """Pull traces from Langfuse and return them as EvalKit-shaped row dicts.

    Each returned dict has ``id`` (the trace id), ``input``, ``output``, and
    ``metadata`` (incl. ``langfuse.trace_id``, ``langfuse.session_id``).

    Raises:
        AdapterError: if the ``langfuse`` package isn't installed.
    """
    try:
        from langfuse import Langfuse  # noqa: PLC0415
    except ImportError as exc:
        raise AdapterError(
            "langfuse not installed. Install with: pip install 'evalkit-oss[langfuse]'",
        ) from exc

    client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
    response = client.fetch_traces(
        from_timestamp=since,
        to_timestamp=until,
        limit=limit,
        name=name,
        user_id=user_id,
    )
    out: list[dict[str, Any]] = []
    for trace in _iter_traces(response):
        out.append(
            {
                "id": str(trace.id),
                "input": _coerce_dict(getattr(trace, "input", None)),
                "output": _coerce_dict(getattr(trace, "output", None)),
                "metadata": {
                    "langfuse": {
                        "trace_id": str(trace.id),
                        "session_id": getattr(trace, "session_id", None),
                        "user_id": getattr(trace, "user_id", None),
                        "name": getattr(trace, "name", None),
                        "tags": list(getattr(trace, "tags", []) or []),
                    },
                },
            },
        )
    return out


def push_score(
    *,
    trace_id: str,
    name: str,
    value: float,
    comment: str | None = None,
    public_key: str | None = None,
    secret_key: str | None = None,
    host: str | None = None,
) -> None:
    """Write a single EvalKit metric score back to Langfuse as a trace observation."""
    try:
        from langfuse import Langfuse  # noqa: PLC0415
    except ImportError as exc:
        raise AdapterError(
            "langfuse not installed. Install with: pip install 'evalkit-oss[langfuse]'",
        ) from exc
    client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
    client.score(trace_id=trace_id, name=name, value=value, comment=comment)


# ---- helpers --------------------------------------------------------------


def _iter_traces(response: Any) -> list[Any]:
    data = getattr(response, "data", None)
    if data is None:
        return []
    out: list[Any] = list(data)
    return out


def _coerce_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    return {"value": value}
