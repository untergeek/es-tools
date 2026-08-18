"""Data-stream selector."""

from __future__ import annotations

from elasticsearch9 import NotFoundError

from ._response import as_mapping
from .context import SelectContext
from .models import DataStreamFilter


def select_data_stream(
    ctx: SelectContext, names: list[str] | None, f: DataStreamFilter
) -> list[str]:
    """Return data-stream or backing-index names.

    Args:
        ctx: Select context.
        names: Current universe, or None to query ES.
        f: Data-stream selector. ``expand`` defaults to ``backing``.

    Returns:
        Stream names or backing index names in API order. Missing streams
        yield an empty list.

    Raises:
        ValueError: ``exclude=True`` used as the first filter.
    """
    try:
        body = as_mapping(ctx.client.indices.get_data_stream(name=f.pattern))
    except NotFoundError:
        body = {}
    streams = body.get("data_streams") or []
    if f.expand == "none":
        found = [str(ds.get("name") or "") for ds in streams if ds.get("name")]
    else:
        found = []
        for ds in streams:
            for idx in ds.get("indices") or []:
                name = idx.get("index") if isinstance(idx, dict) else None
                if name:
                    found.append(str(name))
    if f.exclude:
        if names is None:
            raise ValueError("data_stream exclude=True cannot be first")
        drop = set(found)
        return [n for n in names if n not in drop]
    if names is None:
        return found
    keep = set(found)
    return [n for n in names if n in keep]
