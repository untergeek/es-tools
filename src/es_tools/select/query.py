"""Query DSL selector: indices with matching documents."""

from __future__ import annotations

from typing import Any

from elasticsearch9 import NotFoundError

from es_tools.utils.chunk import chunk_names

from ._response import as_mapping
from .context import SelectContext
from .models import QueryFilter

_MAX_PATTERN = 3072
_TERMS_SIZE = 10000


def select_query(
    ctx: SelectContext, names: list[str] | None, f: QueryFilter
) -> list[str]:
    """Return index names that have hits for ``f.query``.

    Args:
        ctx: Select context.
        names: Current universe, or None to search ``f.index_pattern``.
        f: Query selector.

    Returns:
        Matching index names (or the incoming list minus matches if exclude).
        A 404 search yields an empty list.

    Raises:
        ValueError: Missing pattern, pattern too long, or more than 10000
            index buckets.
    """
    if names is None:
        pattern = f.index_pattern
        if not pattern:
            if not ctx.allow_unbounded:
                raise ValueError("query requires index_pattern unless allow_unbounded")
            pattern = "*"
        if len(pattern) > _MAX_PATTERN:
            raise ValueError("index_pattern longer than 3072")
        found = _search_chunks(ctx, [pattern], f.query)
    else:
        found = _search_chunks(ctx, names, f.query)
    if f.exclude:
        if names is None:
            raise ValueError("query exclude=True cannot be first")
        drop = set(found)
        return [n for n in names if n not in drop]
    return found


def _search_chunks(
    ctx: SelectContext, indexes: list[str], query: dict[str, Any]
) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for chunk in chunk_names(indexes):
        for name in _search_one(ctx, ",".join(chunk), query):
            if name not in seen:
                seen.add(name)
                found.append(name)
    return found


def _search_one(ctx: SelectContext, index: str, query: dict[str, Any]) -> list[str]:
    try:
        resp = ctx.client.search(
            index=index,
            query=query,
            size=0,
            ignore_unavailable=True,
            aggs={
                "matching_indices": {"terms": {"field": "_index", "size": _TERMS_SIZE}}
            },
        )
    except NotFoundError:
        return []
    body = as_mapping(resp)
    agg = (body.get("aggregations") or {}).get("matching_indices") or {}
    if agg.get("sum_other_doc_count"):
        raise ValueError("query matched more than 10000 indices; narrow index_pattern")
    return [str(b["key"]) for b in agg.get("buckets") or []]
