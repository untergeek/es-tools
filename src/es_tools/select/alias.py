"""Alias selector."""

from __future__ import annotations

from elasticsearch9 import NotFoundError

from ._response import as_mapping
from .context import SelectContext
from .models import AliasFilter


def select_alias(
    ctx: SelectContext, names: list[str] | None, f: AliasFilter
) -> list[str]:
    """Return indices that hold ``f.aliases``.

    Args:
        ctx: Select context.
        names: Current universe, or None to query ES.
        f: Alias selector.

    Returns:
        Index names. Missing aliases yield an empty list.

    Raises:
        ValueError: ``exclude=True`` used as the first filter.
    """
    try:
        body = as_mapping(ctx.client.indices.get_alias(name=f.aliases))
    except NotFoundError:
        body = {}
    found = list(body.keys())
    if f.exclude:
        if names is None:
            raise ValueError("alias exclude=True cannot be first")
        drop = set(found)
        return [n for n in names if n not in drop]
    if names is None:
        return found
    keep = set(found)
    return [n for n in names if n in keep]
