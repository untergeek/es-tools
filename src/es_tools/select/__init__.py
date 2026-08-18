"""Index, alias, query, data-stream, and snapshot-indices selectors.

Example:
    >>> from es_tools.select import PatternFilter, SelectContext, apply_filters
    >>> ctx = SelectContext(client=client, target="index")
    >>> apply_filters(ctx, [PatternFilter(pattern_kind="prefix", value="logs-")])
"""

from .context import SelectContext
from .models import (
    AliasFilter,
    DataStreamFilter,
    PatternFilter,
    QueryFilter,
    Selector,
    SnapshotIndicesFilter,
)
from .pipeline import apply_filters

__all__ = [
    "AliasFilter",
    "DataStreamFilter",
    "PatternFilter",
    "QueryFilter",
    "SelectContext",
    "Selector",
    "SnapshotIndicesFilter",
    "apply_filters",
]
