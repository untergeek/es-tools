"""Tests for PatternFilter as snapshot-name selector."""

from __future__ import annotations

from typing import Any

import pytest
from elastic_transport import ApiResponseMeta, HttpHeaders
from elasticsearch9 import NotFoundError

from es_tools.select import PatternFilter, SelectContext, apply_filters


def _not_found() -> NotFoundError:
    meta = ApiResponseMeta(
        status=404,
        http_version="1.1",
        headers=HttpHeaders(),
        duration=0.0,
        node=None,  # type: ignore[arg-type]
    )
    return NotFoundError(
        "not found", meta, {"error": {"type": "repository_missing_exception"}}
    )


class _Snapshot:
    def __init__(self, body: dict[str, Any] | BaseException) -> None:
        self._body = body
        self.calls: list[tuple[str, str]] = []

    def get(self, repository: str, snapshot: str) -> dict[str, Any]:
        self.calls.append((repository, snapshot))
        if isinstance(self._body, BaseException):
            raise self._body
        return self._body


class _Client:
    def __init__(self, body: dict[str, Any] | BaseException) -> None:
        self.snapshot = _Snapshot(body)
        self.cat = None


def _ctx(client: Any, **kw: Any) -> SelectContext:
    return SelectContext(
        client=client, target="snapshot", repository="repo", **kw
    )


def test_snapshot_prefix_uses_snapshot_get_not_cat() -> None:
    """Prefix lists snapshot names via snapshot.get, not cat.indices."""
    client = _Client(
        {
            "snapshots": [
                {"snapshot": "snap-ok"},
                {"snapshot": "snap-bad"},
                {"snapshot": "other"},
            ]
        }
    )
    names = apply_filters(
        _ctx(client),
        [PatternFilter(pattern_kind="prefix", value="snap-")],
    )
    assert names == ["snap-ok", "snap-bad"]
    assert client.snapshot.calls == [("repo", "snap-*")]


def test_snapshot_pattern_requires_repository() -> None:
    ctx = SelectContext(client=_Client({"snapshots": []}), target="snapshot")
    with pytest.raises(ValueError, match="repository"):
        apply_filters(
            ctx, [PatternFilter(pattern_kind="prefix", value="snap-")]
        )


def test_snapshot_pattern_not_found_is_empty() -> None:
    names = apply_filters(
        _ctx(_Client(_not_found())),
        [PatternFilter(pattern_kind="prefix", value="snap-")],
    )
    assert names == []


def test_snapshot_unbounded_requires_flag() -> None:
    ctx = _ctx(_Client({"snapshots": []}))
    with pytest.raises(ValueError, match="allow_unbounded"):
        apply_filters(ctx, [PatternFilter(pattern_kind="prefix", value="")])
