"""Tests for recovery-based wait.Restore."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from es_tools.wait.restore import Restore


def _recovery(*shards_by_index: tuple[str, list[dict]]) -> dict:
    return {name: {"shards": shards} for name, shards in shards_by_index}


def test_rejects_task_id_positional() -> None:
    """Old Restore(client, task_id) API is rejected."""
    with pytest.raises(TypeError, match="task_id"):
        Restore(MagicMock(), "node:1")  # type: ignore


def test_empty_recovery_is_not_done() -> None:
    """Empty cluster recovery means restore has not appeared yet."""
    client = MagicMock()
    client.indices.recovery.return_value = {}
    assert Restore(client).check() is False
    client.indices.recovery.assert_called_once_with()


def test_snapshot_in_progress_is_not_done() -> None:
    """SNAPSHOT shard still in INDEX is incomplete."""
    client = MagicMock()
    in_progress = _recovery(
        ("restored-a", [{"type": "SNAPSHOT", "stage": "INDEX", "primary": True}])
    )
    client.indices.recovery.side_effect = [in_progress, in_progress]
    assert Restore(client).check() is False


def test_all_shards_done_is_complete() -> None:
    """All restore-related shards DONE on the discovered index completes the wait."""
    client = MagicMock()
    done = _recovery(
        (
            "restored-a",
            [
                {"type": "SNAPSHOT", "stage": "DONE", "primary": True},
                {"type": "PEER", "stage": "DONE", "primary": False},
            ],
        )
    )
    client.indices.recovery.side_effect = [done, done]
    assert Restore(client).check() is True
    assert client.indices.recovery.call_args_list[0].args == ()
    assert client.indices.recovery.call_args_list[1].kwargs["index"] == "restored-a"


def test_same_index_peer_recovery_does_not_block_done_restore() -> None:
    """Non-restore shards on the same tracked index do not block completion."""
    client = MagicMock()
    cluster = _recovery(
        (
            "restored-a",
            [
                {"type": "SNAPSHOT", "stage": "DONE", "primary": True},
                {"type": "PEER", "stage": "INDEX", "primary": False},
            ],
        )
    )
    client.indices.recovery.side_effect = [cluster, cluster]
    assert Restore(client).check() is True


def test_same_index_restore_shard_still_controls_completion() -> None:
    """A restore shard in progress keeps waiting even if peer shards are done."""
    client = MagicMock()
    cluster = _recovery(
        (
            "restored-a",
            [
                {"type": "SNAPSHOT", "stage": "INDEX", "primary": True},
                {"type": "PEER", "stage": "DONE", "primary": False},
            ],
        )
    )
    client.indices.recovery.side_effect = [cluster, cluster]
    assert Restore(client).check() is False


def test_unrelated_peer_recovery_is_ignored() -> None:
    """PEER/EXISTING_STORE on other indices do not count as this restore."""
    client = MagicMock()
    cluster = _recovery(
        ("other", [{"type": "PEER", "stage": "INDEX", "primary": False}]),
        ("mine", [{"type": "SNAPSHOT", "stage": "DONE", "primary": True}]),
    )
    targeted = _recovery(
        ("mine", [{"type": "SNAPSHOT", "stage": "DONE", "primary": True}])
    )
    client.indices.recovery.side_effect = [cluster, targeted]
    assert Restore(client).check() is True
    assert client.indices.recovery.call_args_list[1].kwargs["index"] == "mine"


def test_indices_restrictor_ignores_other_snapshot() -> None:
    """Optional indices= intersects with discovered SNAPSHOT names."""
    client = MagicMock()
    cluster = _recovery(
        ("keep", [{"type": "SNAPSHOT", "stage": "DONE", "primary": True}]),
        ("other", [{"type": "SNAPSHOT", "stage": "INDEX", "primary": True}]),
    )
    targeted = _recovery(
        ("keep", [{"type": "SNAPSHOT", "stage": "DONE", "primary": True}])
    )
    client.indices.recovery.side_effect = [cluster, targeted]
    waiter = Restore(client, indices=["keep"])
    assert waiter.check() is True
    assert waiter._tracked == {"keep"}


def test_grows_tracked_set_across_polls() -> None:
    """Indices that appear later are added to the tracked set."""
    client = MagicMock()
    first = _recovery(("a", [{"type": "SNAPSHOT", "stage": "DONE", "primary": True}]))
    # first check: cluster + targeted for a — a is DONE but we return after
    waiter = Restore(client)
    client.indices.recovery.side_effect = [first, first]
    assert waiter.check() is True
    second_cluster = _recovery(
        ("a", [{"type": "SNAPSHOT", "stage": "DONE", "primary": True}]),
        ("b", [{"type": "SNAPSHOT", "stage": "INDEX", "primary": True}]),
    )
    second_target = _recovery(
        ("a", [{"type": "SNAPSHOT", "stage": "DONE", "primary": True}]),
        ("b", [{"type": "SNAPSHOT", "stage": "INDEX", "primary": True}]),
    )
    client.indices.recovery.side_effect = [second_cluster, second_target]
    assert waiter.check() is False
    assert waiter._tracked == {"a", "b"}


def test_tracked_index_without_restore_shards_is_not_done() -> None:
    """A tracked index must still show restore shards in the targeted response."""
    client = MagicMock()
    cluster = _recovery(
        ("restored-a", [{"type": "SNAPSHOT", "stage": "DONE", "primary": True}])
    )
    targeted = _recovery(
        ("restored-a", [{"type": "PEER", "stage": "DONE", "primary": False}])
    )
    client.indices.recovery.side_effect = [cluster, targeted]
    assert Restore(client).check() is False


def test_cluster_recovery_exception_counts_once() -> None:
    """A discovery failure increments the exception counter once."""
    client = MagicMock()
    client.indices.recovery.side_effect = RuntimeError("down")
    waiter = Restore(client)
    assert waiter.check() is False
    assert waiter.exceptions_raised == 1
    assert len(waiter._exceptions) == 1


def test_targeted_recovery_exception_counts_once() -> None:
    """A targeted recovery failure increments the exception counter once."""
    client = MagicMock()
    cluster = _recovery(
        ("restored-a", [{"type": "SNAPSHOT", "stage": "DONE", "primary": True}])
    )
    client.indices.recovery.side_effect = [cluster, RuntimeError("down")]
    waiter = Restore(client)
    assert waiter.check() is False
    assert waiter.exceptions_raised == 1
    assert len(waiter._exceptions) == 1
