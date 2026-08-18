"""Tests for snapshot_indices selector."""

from __future__ import annotations

from typing import Any

import pytest
from elastic_transport import ApiResponseMeta, HttpHeaders
from elasticsearch9 import NotFoundError

from es_tools.select import (
    SelectContext,
    SnapshotIndicesFilter,
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
        "not found", meta, {"error": {"type": "snapshot_missing_exception"}}
    )


class _Snapshot:
    def __init__(self, body: dict[str, Any] | BaseException) -> None:
        self._body = body

    def get(self, repository: str, snapshot: str) -> dict[str, Any]:
        assert repository == "repo"
        assert snapshot == "snap-1"
        if isinstance(self._body, BaseException):
            raise self._body
        return self._body


class _Client:
    def __init__(self, body: dict[str, Any] | BaseException) -> None:
        self.snapshot = _Snapshot(body)


def _ctx(client: Any) -> SelectContext:
    return SelectContext(
        client=client,
        target="index",
        repository="repo",
        snapshot="snap-1",
    )


def test_snapshot_indices_returns_index_names() -> None:
    """snapshot.get indices list is the restore universe."""
    client = _Client(
        {
            "snapshots": [
                {"snapshot": "snap-1", "indices": ["logs-1", "logs-2"]},
            ]
        }
    )
    names = apply_filters(_ctx(client), [SnapshotIndicesFilter()])
    assert names == ["logs-1", "logs-2"]


def test_snapshot_indices_not_found_is_empty() -> None:
    """Missing snapshot is an empty universe."""
    names = apply_filters(_ctx(_Client(_not_found())), [SnapshotIndicesFilter()])
    assert names == []


def test_snapshot_indices_requires_repository() -> None:
    ctx = SelectContext(
        client=_Client({"snapshots": []}),
        target="index",
        snapshot="snap-1",
    )
    with pytest.raises(ValueError, match="repository"):
        apply_filters(ctx, [SnapshotIndicesFilter()])


def test_snapshot_indices_requires_snapshot() -> None:
    ctx = SelectContext(
        client=_Client({"snapshots": []}),
        target="index",
        repository="repo",
    )
    with pytest.raises(ValueError, match="snapshot"):
        apply_filters(ctx, [SnapshotIndicesFilter()])


def test_snapshot_indices_intersects_existing_names() -> None:
    from es_tools.select.snapshot_indices import select_snapshot_indices

    client = _Client(
        {"snapshots": [{"indices": ["logs-1", "logs-2", "other"]}]}
    )
    f = SnapshotIndicesFilter()
    assert select_snapshot_indices(_ctx(client), ["logs-2", "nope"], f) == ["logs-2"]


def test_snapshot_indices_rejects_snapshot_target() -> None:
    """Restore universe is index names; target=snapshot is not this selector."""
    ctx = SelectContext(
        client=_Client({"snapshots": []}),
        target="snapshot",
        repository="repo",
        snapshot="snap-1",
    )
    with pytest.raises(ValueError, match="got 'snapshot'"):
        apply_filters(ctx, [SnapshotIndicesFilter()])
