"""Run a sequence of selectors to produce a name list."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .alias import select_alias
from .context import SelectContext
from .data_stream import select_data_stream
from .models import Selector
from .pattern import select_pattern
from .query import select_query
from .snapshot_indices import select_snapshot_indices

_Dispatch = Callable[[SelectContext, list[str] | None, Any], list[str]]

_DISPATCH: dict[str, _Dispatch] = {
    "pattern": select_pattern,
    "alias": select_alias,
    "query": select_query,
    "data_stream": select_data_stream,
    "snapshot_indices": select_snapshot_indices,
}

_KIND_TARGETS: dict[str, frozenset[str]] = {
    "pattern": frozenset({"index", "snapshot"}),
    "alias": frozenset({"index"}),
    "query": frozenset({"index"}),
    "data_stream": frozenset({"index", "data_stream"}),
    "snapshot_indices": frozenset({"index"}),
}


def apply_filters(ctx: SelectContext, filters: list[Selector]) -> list[str]:
    """Apply selectors in order and return the resolved names.

    Args:
        ctx: Select context.
        filters: Non-empty list of selector models.

    Returns:
        Names with ``ctx.protect`` removed.

    Raises:
        ValueError: Empty filters, exclude-first, unsupported ``target``,
            or a selector error.
    """
    if not filters:
        raise ValueError("filters must be non-empty")
    names: list[str] | None = None
    for i, f in enumerate(filters):
        if names is None and f.exclude:
            raise ValueError(f"filter[{i}] exclude=True cannot be first")
        allowed = _KIND_TARGETS.get(f.kind)
        if allowed is None:
            raise ValueError(f"unknown selector kind: {f.kind!r}")
        if ctx.target not in allowed:
            raise ValueError(
                f"{f.kind} requires target {sorted(allowed)}, got {ctx.target!r}"
            )
        names = _DISPATCH[f.kind](ctx, names, f)
    assert names is not None
    if ctx.protect:
        names = [n for n in names if n not in ctx.protect]
    return names
