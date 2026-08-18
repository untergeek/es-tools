"""Name-pattern selector."""

from __future__ import annotations

import re

from elasticsearch9 import NotFoundError

from ._response import as_list, as_mapping
from .context import SelectContext
from .models import PatternFilter


def select_pattern(
    ctx: SelectContext, names: list[str] | None, f: PatternFilter
) -> list[str]:
    """Filter names by prefix, suffix, or regex.

    Prefix/suffix with ``names is None`` call ``cat.indices`` (or
    ``snapshot.get`` when ``target="snapshot"``) with an ES wildcard.
    Regex is in-memory only unless ``allow_unbounded`` lists ``*``.
    Empty prefix/suffix is unbounded and requires ``allow_unbounded``.

    Args:
        ctx: Select context.
        names: Current universe, or None to query ES.
        f: Pattern selector.

    Returns:
        Matching names.

    Raises:
        ValueError: Regex used as a first filter without ``allow_unbounded``,
            empty prefix/suffix without ``allow_unbounded``, or snapshot
            target without ``repository``.
    """
    _reject_unbounded(ctx, names, f)
    if names is None:
        if ctx.target == "snapshot":
            names = _list_snapshots(ctx, f)
        else:
            wildcard = _wildcard(f)
            rows = as_list(
                ctx.client.cat.indices(index=wildcard, h="index", format="json")
            )
            names = [_row_index(row) for row in rows if _row_index(row)]
        matched = _match(names, f)
        if f.exclude:
            raise ValueError("pattern exclude=True cannot be first")
        return matched
    matched = _match(names, f)
    if f.exclude:
        keep = set(matched)
        return [n for n in names if n not in keep]
    return matched


def _reject_unbounded(
    ctx: SelectContext, names: list[str] | None, f: PatternFilter
) -> None:
    if f.pattern_kind == "regex":
        if names is None and not ctx.allow_unbounded:
            raise ValueError("regex is not a selector")
        return
    if ctx.allow_unbounded:
        return
    if not f.value or _wildcard(f) == "*":
        raise ValueError("unbounded pattern requires allow_unbounded")


def _wildcard(f: PatternFilter) -> str:
    if f.pattern_kind == "prefix":
        return f"{f.value}*"
    if f.pattern_kind == "suffix":
        return f"*{f.value}"
    return "*"


def _list_snapshots(ctx: SelectContext, f: PatternFilter) -> list[str]:
    if not ctx.repository:
        raise ValueError("snapshot pattern requires SelectContext.repository")
    wildcard = _wildcard(f)
    try:
        body = as_mapping(
            ctx.client.snapshot.get(repository=ctx.repository, snapshot=wildcard)
        )
    except NotFoundError:
        body = {}
    names: list[str] = []
    seen: set[str] = set()
    for snap in body.get("snapshots") or []:
        if not isinstance(snap, dict):
            continue
        name = snap.get("snapshot")
        if isinstance(name, str) and name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _match(names: list[str], f: PatternFilter) -> list[str]:
    if f.pattern_kind == "prefix":
        return [n for n in names if n.startswith(f.value)]
    if f.pattern_kind == "suffix":
        return [n for n in names if n.endswith(f.value)]
    cre = re.compile(f.value)
    return [n for n in names if cre.search(n)]


def _row_index(row: object) -> str:
    if isinstance(row, dict):
        return str(row.get("index") or "")
    return str(row)
