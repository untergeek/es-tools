"""Tests for UpdateAliases."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from es_tools.checkpoint.action_run import ActionRun
from es_tools.checkpoint.event_bus import EventBus
from es_tools.index.actions import UpdateAliases


def test_alias_rejects_empty_add_and_remove() -> None:
    """Ctor requires at least one add or remove name."""
    with pytest.raises(ValueError, match="add and remove"):
        UpdateAliases("logs-write")


def test_alias_rejects_empty_alias_name() -> None:
    """Alias name must be non-empty."""
    with pytest.raises(ValueError, match="alias"):
        UpdateAliases("", add=["a"])


def test_alias_add_only_one_update() -> None:
    """Add-only builds add actions and does not call get_alias."""
    action = UpdateAliases(
        "logs-write", add=["a", "b"], extra_settings={"is_write_index": True}
    )
    client = MagicMock()
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(action, action.names)
    client.indices.get_alias.assert_not_called()
    client.indices.update_aliases.assert_called_once_with(
        actions=[
            {"add": {"index": "a", "alias": "logs-write", "is_write_index": True}},
            {"add": {"index": "b", "alias": "logs-write", "is_write_index": True}},
        ]
    )
    assert len(wb.jobs) == 1
    assert wb.jobs[0].index == "alias:2"
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1"]
    assert wb.status == "COMPLETED"


def test_alias_remove_skips_non_holders() -> None:
    """Remove only emits ops for indices that currently hold the alias."""
    action = UpdateAliases("logs-write", remove=["a", "b", "c"])
    client = MagicMock()
    client.indices.get_alias.return_value = {
        "a": {"aliases": {"logs-write": {}}},
        "b": {"aliases": {"other": {}}},
    }
    ActionRun(client, EventBus(), "es-checkpoint").run(action, action.names)
    client.indices.get_alias.assert_called_once_with(
        index="a,b,c",
        expand_wildcards=["open", "closed"],
    )
    client.indices.update_aliases.assert_called_once_with(
        actions=[{"remove": {"index": "a", "alias": "logs-write"}}]
    )


def test_alias_add_and_remove_single_call() -> None:
    """Add and remove share one update_aliases call."""
    action = UpdateAliases("logs-write", add=["new"], remove=["old"])
    client = MagicMock()
    client.indices.get_alias.return_value = {
        "old": {"aliases": {"logs-write": {}}},
    }
    ActionRun(client, EventBus(), "es-checkpoint").run(action, action.names)
    client.indices.get_alias.assert_called_once_with(
        index="old",
        expand_wildcards=["open", "closed"],
    )
    assert client.indices.update_aliases.call_count == 1
    actions = client.indices.update_aliases.call_args.kwargs["actions"]
    assert {"add": {"index": "new", "alias": "logs-write"}} in actions
    assert {"remove": {"index": "old", "alias": "logs-write"}} in actions


def test_alias_remove_all_skipped_is_success() -> None:
    """If no remove target holds the alias, skip update_aliases and succeed."""
    action = UpdateAliases("logs-write", remove=["a"])
    client = MagicMock()
    client.indices.get_alias.return_value = {}
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(action, action.names)
    client.indices.update_aliases.assert_not_called()
    assert wb.status == "COMPLETED"


def test_alias_dry_run_skips_es() -> None:
    """dry_run emits the execute Step and does not call ES."""
    action = UpdateAliases("logs-write", add=["a"])
    client = MagicMock()
    wb = ActionRun(client, EventBus(), "es-checkpoint", dry_run=True).run(
        action, action.names
    )
    client.indices.update_aliases.assert_not_called()
    client.indices.get_alias.assert_not_called()
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1"]
    assert wb.status == "COMPLETED"
