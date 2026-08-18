"""Normalize Elasticsearch client responses to plain dicts and lists."""

from __future__ import annotations

from typing import Any


def as_mapping(raw: Any) -> dict[str, Any]:
    """Return a dict from an ES response or mapping-like object.

    Args:
        raw: Client return value.

    Returns:
        A plain dict. Non-mappings become ``{}``.
    """
    if raw is None:
        return {}
    if hasattr(raw, "body"):
        raw = raw.body
    if isinstance(raw, dict):
        return raw
    try:
        return dict(raw)
    except (TypeError, ValueError):
        return {}


def as_list(raw: Any) -> list[Any]:
    """Return a list from an ES cat-style response.

    Args:
        raw: Client return value.

    Returns:
        A plain list.
    """
    if raw is None:
        return []
    if hasattr(raw, "body"):
        raw = raw.body
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return [raw]
    try:
        return list(raw)
    except (TypeError, ValueError):
        return []
