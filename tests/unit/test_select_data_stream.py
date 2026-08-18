"""Tests for es_tools.select data_stream selector."""

from __future__ import annotations

from typing import Any

from elastic_transport import ApiResponseMeta, HttpHeaders
from elasticsearch9 import NotFoundError

from es_tools.select import DataStreamFilter, SelectContext, apply_filters


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
    def get_data_stream(self, name: str | None = None) -> dict[str, Any]:
        assert name == "logs-*"
        return {
            "data_streams": [
                {
                    "name": "logs-nginx",
                    "indices": [
                        {"index": ".ds-logs-nginx-000001"},
                        {"index": ".ds-logs-nginx-000002"},
                    ],
                }
            ]
        }


class _Client:
    def __init__(self) -> None:
        self.indices = _Indices()


def test_data_stream_expands_backing_by_default() -> None:
    ctx = SelectContext(client=_Client(), target="index")
    names = apply_filters(ctx, [DataStreamFilter(pattern="logs-*")])
    assert names == [".ds-logs-nginx-000001", ".ds-logs-nginx-000002"]


def test_data_stream_expand_none() -> None:
    ctx = SelectContext(client=_Client(), target="index")
    names = apply_filters(
        ctx, [DataStreamFilter(pattern="logs-*", expand="none")]
    )
    assert names == ["logs-nginx"]


def test_data_stream_allows_data_stream_target() -> None:
    ctx = SelectContext(client=_Client(), target="data_stream")
    names = apply_filters(
        ctx, [DataStreamFilter(pattern="logs-*", expand="none")]
    )
    assert names == ["logs-nginx"]


class _MissingStream:
    def get_data_stream(self, name: str | None = None) -> dict[str, Any]:
        raise _not_found()


def test_data_stream_not_found_returns_empty() -> None:
    ctx = SelectContext(
        client=type("C", (), {"indices": _MissingStream()})(),
        target="index",
    )
    assert apply_filters(ctx, [DataStreamFilter(pattern="no-such")]) == []
