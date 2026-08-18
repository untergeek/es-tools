"""Snapshot-contents selector: index names inside one snapshot."""

from __future__ import annotations

from elasticsearch9 import NotFoundError

from ._response import as_mapping
from .context import SelectContext
from .models import SnapshotIndicesFilter


def select_snapshot_indices(
    ctx: SelectContext,
    names: list[str] | None,
    f: SnapshotIndicesFilter,
) -> list[str]:
    """Return index names stored in ``ctx.snapshot``.

    Args:
        ctx: Select context with ``repository`` and ``snapshot`` set.
        names: Current universe, or None to use the snapshot's index list.
        f: Snapshot-indices selector.

    Returns:
        Index names in API order. Missing snapshot yields an empty list.

    Raises:
        ValueError: ``repository`` or ``snapshot`` missing on ``ctx``,
            or ``exclude=True`` used as the first filter.
    """
    if not ctx.repository:
        raise ValueError("snapshot_indices requires SelectContext.repository")
    if not ctx.snapshot:
        raise ValueError("snapshot_indices requires SelectContext.snapshot")
    try:
        body = as_mapping(
            ctx.client.snapshot.get(
                repository=ctx.repository, snapshot=ctx.snapshot
            )
        )
    except NotFoundError:
        body = {}
    found: list[str] = []
    seen: set[str] = set()
    for snap in body.get("snapshots") or []:
        if not isinstance(snap, dict):
            continue
        for idx in snap.get("indices") or []:
            name = idx if isinstance(idx, str) else ""
            if name and name not in seen:
                seen.add(name)
                found.append(name)
    if f.exclude:
        if names is None:
            raise ValueError("snapshot_indices exclude=True cannot be first")
        drop = set(found)
        return [n for n in names if n not in drop]
    if names is None:
        return found
    keep = set(found)
    return [n for n in names if n in keep]
