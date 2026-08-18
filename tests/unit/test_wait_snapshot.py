"""Tests for Snapshot waiter terminal states and name matching."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from es_tools.exceptions import ESToolWaitFatal
from es_tools.wait.snapshot import Snapshot


def test_success_true() -> None:
    """SUCCESS is done."""
    client = MagicMock()
    client.snapshot.get.return_value = {
        "snapshots": [{"snapshot": "snap_1", "state": "SUCCESS"}]
    }
    assert Snapshot(client, "repo", "snap_1").check() is True


def test_in_progress_false() -> None:
    """IN_PROGRESS keeps waiting."""
    client = MagicMock()
    client.snapshot.get.return_value = {
        "snapshots": [{"snapshot": "snap_1", "state": "IN_PROGRESS"}]
    }
    assert Snapshot(client, "repo", "snap_1").check() is False


@pytest.mark.parametrize("state", ["FAILED", "PARTIAL", "INCOMPATIBLE"])
def test_terminal_raises(state: str) -> None:
    """FAILED / PARTIAL / INCOMPATIBLE raise immediately."""
    client = MagicMock()
    client.snapshot.get.return_value = {
        "snapshots": [{"snapshot": "snap_1", "state": state}]
    }
    with pytest.raises(ESToolWaitFatal, match=state):
        Snapshot(client, "repo", "snap_1").check()


def test_matches_by_name_not_first() -> None:
    """Match the named snapshot, not snapshots[0]."""
    client = MagicMock()
    client.snapshot.get.return_value = {
        "snapshots": [
            {"snapshot": "other", "state": "SUCCESS"},
            {"snapshot": "snap_1", "state": "IN_PROGRESS"},
        ]
    }
    assert Snapshot(client, "repo", "snap_1").check() is False


def test_snapshot_exception_counts_once() -> None:
    """A single snapshot polling failure increments the counter once."""
    client = MagicMock()
    client.snapshot.get.side_effect = RuntimeError("down")
    waiter = Snapshot(client, "repo", "snap_1")
    assert waiter.check() is False
    assert waiter.exceptions_raised == 1
    assert len(waiter._exceptions) == 1
