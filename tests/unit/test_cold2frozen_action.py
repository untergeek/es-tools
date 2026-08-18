"""Tests for Cold2FrozenIndices pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from es_tools.checkpoint.action_run import ActionRun
from es_tools.checkpoint.event_bus import EventBus
from es_tools.index.actions import Cold2FrozenIndices


def _cold_body(source: str = "logs-1") -> dict:
    return {
        source: {
            "settings": {
                "index": {
                    "store": {
                        "snapshot": {
                            "snapshot_name": "snap-1",
                            "index_name": "snap-idx",
                            "repository_name": "repo",
                        }
                    }
                }
            },
            "aliases": {"logs-write": {}},
        }
    }


def _frozen_body(target: str) -> dict:
    return {
        target: {
            "settings": {
                "index": {"store": {"snapshot": {"partial": True}}},
            },
            "aliases": {},
        }
    }


def test_cold2frozen_rejects_empty_prefix() -> None:
    """renamed_prefix must be non-empty."""
    with pytest.raises(ValueError, match="renamed_prefix"):
        Cold2FrozenIndices(renamed_prefix="")


def test_cold2frozen_pipeline_mounts_and_cleans() -> None:
    """inspect → mount → verify → aliases → delete."""
    client = MagicMock()
    source = "logs-1"
    target = "partial-logs-1"

    def _get(*, index: str) -> dict:
        if index == source:
            return _cold_body(source)
        if index == target:
            return _frozen_body(target)
        raise AssertionError(index)

    client.indices.get.side_effect = _get
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(
        Cold2FrozenIndices(), [source]
    )
    assert [s.name for s in wb.jobs[0].steps] == [
        "inspect-1",
        "mount-1",
        "verify-1",
        "aliases-1",
        "delete-1",
    ]
    client.searchable_snapshots.mount.assert_called_once_with(
        repository="repo",
        snapshot="snap-1",
        index="snap-idx",
        renamed_index=target,
        storage="shared_cache",
        wait_for_completion=True,
        ignore_index_settings=["index.refresh_interval"],
    )
    actions = client.indices.update_aliases.call_args.kwargs["actions"]
    assert {"remove": {"index": source, "alias": "logs-write"}} in actions
    assert {"add": {"index": target, "alias": "logs-write"}} in actions
    client.indices.delete.assert_called_once_with(index=source)
    assert wb.jobs[0].index == "cold2frozen:1"
    assert wb.status == "COMPLETED"


def test_mount_does_not_depend_on_instance_info() -> None:
    """Mount re-reads snapshot coords; it does not need inspect's _info bag."""
    action = Cold2FrozenIndices()
    client = MagicMock()
    client.indices.get.return_value = _cold_body("logs-1")
    result = action._mount(client, "logs-1")
    assert result.ok
    client.searchable_snapshots.mount.assert_called_once()


def test_cold2frozen_rejects_ilm() -> None:
    """ILM-managed indices fail inspect."""
    client = MagicMock()
    client.indices.get.return_value = {
        "logs-1": {
            "settings": {"index": {"lifecycle": {"name": "policy"}}},
            "aliases": {},
        }
    }
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(
        Cold2FrozenIndices(), ["logs-1"]
    )
    assert wb.jobs[0].steps[0].status == "FAILED"
    assert "ILM" in (wb.jobs[0].steps[0]._error or "")
    client.searchable_snapshots.mount.assert_not_called()
    assert wb.status == "CANCELLED"


def test_cold2frozen_rejects_already_frozen() -> None:
    """Already-partial mounts fail inspect."""
    client = MagicMock()
    client.indices.get.return_value = {
        "logs-1": {
            "settings": {
                "index": {"store": {"snapshot": {"partial": True}}},
            },
            "aliases": {},
        }
    }
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(
        Cold2FrozenIndices(), ["logs-1"]
    )
    assert wb.jobs[0].steps[0].status == "FAILED"
    assert "frozen" in (wb.jobs[0].steps[0]._error or "")
    client.searchable_snapshots.mount.assert_not_called()


def test_cold2frozen_can_keep_source_and_skip_aliases() -> None:
    """Flags drop the aliases and delete Steps."""
    client = MagicMock()
    source = "logs-1"
    target = "partial-logs-1"

    def _get(*, index: str) -> dict:
        if index == source:
            return _cold_body(source)
        return _frozen_body(target)

    client.indices.get.side_effect = _get
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(
        Cold2FrozenIndices(transfer_aliases=False, delete_after=False),
        [source],
    )
    assert [s.name for s in wb.jobs[0].steps] == [
        "inspect-1",
        "mount-1",
        "verify-1",
    ]
    client.indices.update_aliases.assert_not_called()
    client.indices.delete.assert_not_called()
    assert wb.status == "COMPLETED"


def test_cold2frozen_dry_run_skips_es() -> None:
    """dry_run emits pipeline Steps and does not call ES."""
    client = MagicMock()
    wb = ActionRun(client, EventBus(), "es-checkpoint", dry_run=True).run(
        Cold2FrozenIndices(), ["logs-1"]
    )
    client.indices.get.assert_not_called()
    client.searchable_snapshots.mount.assert_not_called()
    assert [s.name for s in wb.jobs[0].steps] == [
        "inspect-1",
        "mount-1",
        "verify-1",
        "aliases-1",
        "delete-1",
    ]
