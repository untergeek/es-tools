"""Tests for snapshot list actions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from es_tools.checkpoint.action_run import ActionRun
from es_tools.checkpoint.event_bus import EventBus
from es_tools.snapshot.actions import (
    CreateSnapshot,
    DeleteSnapshots,
    RestoreSnapshot,
)


def test_create_snapshot_called_once_with_full_list() -> None:
    """Snapshot create is one body call; names are not URI-chunked."""
    client = MagicMock()
    client.snapshot.create.return_value = {"accepted": True}
    names = [f"idx-{i}" for i in range(5)]
    with patch("es_tools.wait.snapshot.Snapshot") as snap_wait:
        wb = ActionRun(client, EventBus(), "es-checkpoint").run(
            CreateSnapshot(repository="repo", snapshot="snap-1"),
            names,
        )
    client.snapshot.create.assert_called_once()
    kw = client.snapshot.create.call_args.kwargs
    assert kw["repository"] == "repo"
    assert kw["snapshot"] == "snap-1"
    assert kw["wait_for_completion"] is False
    assert kw["indices"] == names
    assert len(wb.jobs) == 1
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1", "wait-1"]
    snap_wait.assert_called_once()
    assert snap_wait.call_args.kwargs["timeout"] == 7200.0


def test_create_snapshot_does_not_use_chunk_names() -> None:
    """chunk_names must not be consulted for snapshot create."""
    client = MagicMock()
    client.snapshot.create.return_value = {}
    with patch("es_tools.checkpoint.action_run.chunk_names") as chunk:
        ActionRun(client, EventBus(), "es-checkpoint").run(
            CreateSnapshot("repo", "s"),
            ["a", "b"],
            wait_for_completion=False,
        )
    chunk.assert_not_called()


def test_restore_accepted_waits_on_recovery() -> None:
    """Accepted restore still runs the recovery waiter (no task_id)."""
    client = MagicMock()
    client.snapshot.restore.return_value = {"accepted": True}
    with patch("es_tools.wait.restore.Restore") as restore_wait:
        wb = ActionRun(client, EventBus(), "es-checkpoint").run(
            RestoreSnapshot("repo", "s"),
            ["a"],
        )
    client.snapshot.restore.assert_called_once()
    assert client.snapshot.restore.call_args.kwargs["wait_for_completion"] is False
    restore_wait.assert_called_once()
    assert restore_wait.call_args.kwargs.get("task_id") is None
    assert restore_wait.call_args.kwargs["indices"] == ["a"]
    assert restore_wait.call_args.kwargs["repository"] == "repo"
    assert restore_wait.call_args.kwargs["snapshot"] == "s"
    assert restore_wait.call_args.kwargs["timeout"] == 7200.0
    assert wb.status == "COMPLETED"
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1", "wait-1"]


def test_delete_snapshots_one_step_each() -> None:
    """Each snapshot name is its own Step."""
    client = MagicMock()
    client.snapshot.delete.return_value = {"acknowledged": True}
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(
        DeleteSnapshots("repo"),
        ["s1", "s2"],
    )
    assert client.snapshot.delete.call_count == 2
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1", "execute-2"]
    assert len(wb.jobs) == 1


def test_create_requires_repo() -> None:
    """Repository and snapshot names are required."""
    with pytest.raises(ValueError, match="repository"):
        CreateSnapshot("", "s")
