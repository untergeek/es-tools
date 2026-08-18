"""Tests for es_tools.select alias selector."""

from __future__ import annotations

from typing import Any

import pytest
from elastic_transport import ApiResponseMeta, HttpHeaders
from elasticsearch9 import NotFoundError

from es_tools.select import AliasFilter, PatternFilter, SelectContext, apply_filters


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


class _Indices:
    def get_alias(self, name: list[str] | None = None) -> dict[str, Any]:
        assert name == ["my-alias"]
        return {"idx-1": {"aliases": {"my-alias": {}}}}


class _Client:
    def __init__(self) -> None:
        self.indices = _Indices()


def test_alias_returns_holders() -> None:
    ctx = SelectContext(client=_Client(), target="index")
    names = apply_filters(ctx, [AliasFilter(aliases=["my-alias"])])
    assert names == ["idx-1"]


class _MissingAlias:
    def get_alias(self, name: list[str] | None = None) -> dict[str, Any]:
        raise _not_found()


def test_alias_not_found_returns_empty() -> None:
    ctx = SelectContext(client=type("C", (), {"indices": _MissingAlias()})(), target="index")
    assert apply_filters(ctx, [AliasFilter(aliases=["no-such"])]) == []


class _BoomAlias:
    def get_alias(self, name: list[str] | None = None) -> dict[str, Any]:
        raise RuntimeError("cluster down")


def test_alias_other_error_propagates() -> None:
    ctx = SelectContext(client=type("C", (), {"indices": _BoomAlias()})(), target="index")
    with pytest.raises(RuntimeError, match="cluster down"):
        apply_filters(ctx, [AliasFilter(aliases=["my-alias"])])


class _ExcludeClient:
    def __init__(self) -> None:
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
        self.indices = type(
            "Idx",
            (),
            {
                "get_alias": staticmethod(
                    lambda name=None: {"logs-000001": {"aliases": {"my-alias": {}}}}
                )
            },
        )()


def test_alias_exclude_as_second() -> None:
    ctx = SelectContext(client=_ExcludeClient(), target="index")
    names = apply_filters(
        ctx,
        [
            PatternFilter(pattern_kind="prefix", value="logs-"),
            AliasFilter(aliases=["my-alias"], exclude=True),
        ],
    )
    assert names == ["logs-000002"]
