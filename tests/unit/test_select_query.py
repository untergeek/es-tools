"""Tests for es_tools.select query selector."""

from __future__ import annotations

from typing import Any

import pytest
from elastic_transport import ApiResponseMeta, HttpHeaders
from elasticsearch9 import NotFoundError

from es_tools.select import (
    PatternFilter,
    QueryFilter,
    SelectContext,
    apply_filters,
)


def _not_found() -> NotFoundError:
    meta = ApiResponseMeta(
        status=404,
        http_version="1.1",
        headers=HttpHeaders(),
        duration=0.0,
        node=None,  # type: ignore[arg-type]
    )
    return NotFoundError(
        "not found", meta, {"error": {"type": "resource_not_found_exception"}}
    )


def test_query_requires_pattern() -> None:
    ctx = SelectContext(client=object(), target="index")
    with pytest.raises(ValueError, match="index_pattern"):
        apply_filters(ctx, [QueryFilter(query={"match_all": {}})])


class _SearchClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def search(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.response


def _buckets(*names: str, other: int = 0) -> dict[str, Any]:
    return {
        "aggregations": {
            "matching_indices": {
                "buckets": [{"key": n} for n in names],
                "sum_other_doc_count": other,
            }
        }
    }


def test_query_returns_term_buckets() -> None:
    client = _SearchClient(_buckets("logs-a", "logs-b"))
    ctx = SelectContext(client=client, target="index")
    names = apply_filters(
        ctx,
        [QueryFilter(query={"match_all": {}}, index_pattern="logs-*")],
    )
    assert names == ["logs-a", "logs-b"]
    assert client.calls[0]["index"] == "logs-*"
    assert client.calls[0]["size"] == 0
    assert client.calls[0]["ignore_unavailable"] is True


def test_query_overflow_raises() -> None:
    client = _SearchClient(_buckets("logs-a", other=1))
    ctx = SelectContext(client=client, target="index")
    with pytest.raises(ValueError, match="10000"):
        apply_filters(
            ctx,
            [QueryFilter(query={"match_all": {}}, index_pattern="logs-*")],
        )


def test_query_pattern_too_long() -> None:
    ctx = SelectContext(client=object(), target="index")
    with pytest.raises(ValueError, match="3072"):
        apply_filters(
            ctx,
            [QueryFilter(query={"match_all": {}}, index_pattern="x" * 3073)],
        )


def test_query_unbounded_uses_star() -> None:
    client = _SearchClient(_buckets("a"))
    ctx = SelectContext(client=client, target="index", allow_unbounded=True)
    names = apply_filters(ctx, [QueryFilter(query={"match_all": {}})])
    assert names == ["a"]
    assert client.calls[0]["index"] == "*"


class _ComposeClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []
        self.cat = type(
            "Cat",
            (),
            {
                "indices": staticmethod(
                    lambda index=None, **kwargs: [
                        {"index": "logs-000001"},
                        {"index": "logs-000002"},
                    ]
                )
            },
        )()

    def search(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.response


def test_query_filters_incoming_names() -> None:
    client = _ComposeClient(_buckets("logs-000001"))
    ctx = SelectContext(client=client, target="index")
    names = apply_filters(
        ctx,
        [
            PatternFilter(pattern_kind="prefix", value="logs-"),
            QueryFilter(query={"match_all": {}}),
        ],
    )
    assert names == ["logs-000001"]
    assert client.calls[0]["index"] == "logs-000001,logs-000002"
    assert client.calls[0]["ignore_unavailable"] is True


def test_query_exclude_as_second() -> None:
    client = _ComposeClient(_buckets("logs-000001"))
    ctx = SelectContext(client=client, target="index")
    names = apply_filters(
        ctx,
        [
            PatternFilter(pattern_kind="prefix", value="logs-"),
            QueryFilter(query={"match_all": {}}, exclude=True),
        ],
    )
    assert names == ["logs-000002"]


class _MissingSearch:
    def search(self, **kwargs: Any) -> dict[str, Any]:
        raise _not_found()


def test_query_not_found_returns_empty() -> None:
    ctx = SelectContext(client=_MissingSearch(), target="index")
    assert (
        apply_filters(
            ctx,
            [QueryFilter(query={"match_all": {}}, index_pattern="logs-*")],
        )
        == []
    )


class _BoomSearch:
    def search(self, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("cluster down")


def test_query_other_error_propagates() -> None:
    ctx = SelectContext(client=_BoomSearch(), target="index")
    with pytest.raises(RuntimeError, match="cluster down"):
        apply_filters(
            ctx,
            [QueryFilter(query={"match_all": {}}, index_pattern="logs-*")],
        )
