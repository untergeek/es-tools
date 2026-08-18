"""Context for index, snapshot, and data-stream selectors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class SelectContext:
    """Runtime context for ``apply_filters``.

    Args:
        client: Elasticsearch client.
        target: Name kind the pipeline is resolving.
        repository: Snapshot repository for ``target="snapshot"`` pattern
            and for ``snapshot_indices``.
        snapshot: Snapshot name for ``snapshot_indices``.
        allow_unbounded: If True, query/pattern may use ``*``.
        protect: Names always removed from the result (e.g. tracking index).
    """

    client: Any
    target: Literal["index", "snapshot", "data_stream"]
    repository: str | None = None
    snapshot: str | None = None
    allow_unbounded: bool = False
    protect: frozenset[str] = field(default_factory=frozenset)
