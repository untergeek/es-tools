"""Pydantic selector models for ``es_tools.select``."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class FilterBase(BaseModel):
    """Shared selector fields.

    Args:
        exclude: If True, drop matches instead of keeping them.
    """

    exclude: bool = False


class PatternFilter(FilterBase):
    """Select names by prefix, suffix, or regex.

    Args:
        kind: Discriminator; always ``pattern``.
        pattern_kind: How ``value`` is interpreted.
        value: Prefix, suffix, or regex body.
    """

    kind: Literal["pattern"] = "pattern"
    pattern_kind: Literal["prefix", "suffix", "regex"]
    value: str


class AliasFilter(FilterBase):
    """Select indices that hold one or more aliases.

    Args:
        kind: Discriminator; always ``alias``.
        aliases: Alias names passed to ``indices.get_alias``.
    """

    kind: Literal["alias"] = "alias"
    aliases: list[str]


class QueryFilter(FilterBase):
    """Select indices that have documents matching Query DSL.

    Args:
        kind: Discriminator; always ``query``.
        query: Elasticsearch query body.
        index_pattern: Search target when the pipeline has no names yet.
    """

    kind: Literal["query"] = "query"
    query: dict[str, Any]
    index_pattern: str | None = None


class DataStreamFilter(FilterBase):
    """Select data streams, optionally expanding to backing indices.

    Args:
        kind: Discriminator; always ``data_stream``.
        pattern: Data-stream name wildcard (e.g. ``logs-*``).
        expand: ``backing`` (default) or ``none`` (stream names).
    """

    kind: Literal["data_stream"] = "data_stream"
    pattern: str
    expand: Literal["none", "backing"] = "backing"


class SnapshotIndicesFilter(FilterBase):
    """Select index names stored in one snapshot (restore universe).

    Args:
        kind: Discriminator; always ``snapshot_indices``.
    """

    kind: Literal["snapshot_indices"] = "snapshot_indices"


Selector = Annotated[
    PatternFilter
    | AliasFilter
    | QueryFilter
    | DataStreamFilter
    | SnapshotIndicesFilter,
    Field(discriminator="kind"),
]
