"""Tests for apply_filters pipeline guards."""

from __future__ import annotations

import pytest

from es_tools.select import (
    AliasFilter,
    DataStreamFilter,
    PatternFilter,
    SelectContext,
    apply_filters,
)


class _Cat:
    def indices(self, index: str | None = None, **kwargs: object) -> list[dict[str, str]]:
        assert index == "*"
        return [
            {"index": "logs-1"},
            {"index": "es-steward-journal"},
        ]


class _Client:
    def __init__(self) -> None:
        self.cat = _Cat()


def test_protect_strips_tracking_index() -> None:
    ctx = SelectContext(
        client=_Client(),
        target="index",
        allow_unbounded=True,
        protect=frozenset({"es-steward-journal"}),
    )
    names = apply_filters(
        ctx, [PatternFilter(pattern_kind="prefix", value="")]
    )
    assert "es-steward-journal" not in names
    assert "logs-1" in names


def test_empty_filters_raise() -> None:
    ctx = SelectContext(client=object(), target="index")
    with pytest.raises(ValueError, match="non-empty"):
        apply_filters(ctx, [])


def test_exclude_cannot_be_first() -> None:
    ctx = SelectContext(client=object(), target="index")
    with pytest.raises(ValueError, match="cannot be first"):
        apply_filters(
            ctx,
            [PatternFilter(pattern_kind="prefix", value="logs-", exclude=True)],
        )


def test_snapshot_target_uses_kind_map() -> None:
    """alias is still index-only; pattern is allowed on target=snapshot."""
    ctx = SelectContext(client=object(), target="snapshot")
    with pytest.raises(ValueError, match="got 'snapshot'"):
        apply_filters(ctx, [AliasFilter(aliases=["logs"])])


def test_pattern_rejects_data_stream_target() -> None:
    ctx = SelectContext(client=object(), target="data_stream")
    with pytest.raises(ValueError, match="index"):
        apply_filters(
            ctx, [PatternFilter(pattern_kind="prefix", value="logs-")]
        )


def test_query_rejects_data_stream_target() -> None:
    from es_tools.select import QueryFilter

    ctx = SelectContext(client=object(), target="data_stream")
    with pytest.raises(ValueError, match="index"):
        apply_filters(
            ctx,
            [QueryFilter(query={"match_all": {}}, index_pattern="logs-*")],
        )


def test_data_stream_filter_rejects_wrong_kind_on_snapshot() -> None:
    ctx = SelectContext(client=object(), target="snapshot")
    with pytest.raises(ValueError, match="got 'snapshot'"):
        apply_filters(ctx, [DataStreamFilter(pattern="logs-*")])
