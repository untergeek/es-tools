"""Tests for SetClusterRouting cluster action."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from es_tools.checkpoint.action_run import ActionRun
from es_tools.checkpoint.event_bus import EventBus
from es_tools.cluster.actions import SetClusterRouting


def test_valid_allocation_settings() -> None:
    """Valid allocation values construct without error."""
    for value in ["all", "primaries", "new_primaries", "none"]:
        action = SetClusterRouting(
            routing_type="allocation", setting="enable", value=value
        )
        assert action.settings == {"cluster.routing.allocation.enable": value}


def test_valid_rebalance_settings() -> None:
    """Valid rebalance values construct without error."""
    for value in ["all", "primaries", "replicas", "none"]:
        action = SetClusterRouting(
            routing_type="rebalance", setting="enable", value=value
        )
        assert action.settings == {"cluster.routing.rebalance.enable": value}


def test_invalid_setting_raises() -> None:
    """setting must be 'enable'."""
    with pytest.raises(ValueError, match="setting"):
        SetClusterRouting(routing_type="allocation", setting="disable", value="all")


def test_invalid_routing_type_raises() -> None:
    """routing_type must be allocation or rebalance."""
    with pytest.raises(ValueError, match="routing_type"):
        SetClusterRouting(routing_type="shards", setting="enable", value="all")


def test_invalid_allocation_value_raises() -> None:
    """allocation values are a fixed set."""
    with pytest.raises(ValueError, match="value"):
        SetClusterRouting(routing_type="allocation", setting="enable", value="replicas")


def test_invalid_rebalance_value_raises() -> None:
    """rebalance values are a fixed set."""
    with pytest.raises(ValueError, match="value"):
        SetClusterRouting(
            routing_type="rebalance", setting="enable", value="new_primaries"
        )


def test_execute_calls_put_settings_transient() -> None:
    """execute calls cluster.put_settings(transient=...) once."""
    client = MagicMock()
    client.cluster.put_settings.return_value = {"acknowledged": True}
    mock_relocate = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("es_tools.wait.relocate.Relocate", mock_relocate)
        wb = ActionRun(client, EventBus(), "es-checkpoint").run(
            SetClusterRouting("allocation", "enable", "primaries"),
            ["cluster"],
        )
    client.cluster.put_settings.assert_called_once_with(
        transient={"cluster.routing.allocation.enable": "primaries"}
    )
    mock_relocate.assert_called_once()
    assert mock_relocate.call_args.kwargs["mode"] == "all"
    assert wb.status == "COMPLETED"
    assert wb.jobs[0].index == "cluster_routing:1"


def test_execute_no_wait_skips_relocate() -> None:
    """wait_for_completion=False skips the Relocate waiter."""
    client = MagicMock()
    client.cluster.put_settings.return_value = {"acknowledged": True}
    mock_relocate = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("es_tools.wait.relocate.Relocate", mock_relocate)
        wb = ActionRun(client, EventBus(), "es-checkpoint").run(
            SetClusterRouting("allocation", "enable", "none"),
            ["cluster"],
            wait_for_completion=False,
        )
    mock_relocate.assert_not_called()
    assert wb.status == "COMPLETED"


def test_dry_run_makes_no_es_calls() -> None:
    """dry_run=True skips ES entirely."""
    client = MagicMock()
    mock_relocate = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("es_tools.wait.relocate.Relocate", mock_relocate)
        wb = ActionRun(client, EventBus(), "es-checkpoint", dry_run=True).run(
            SetClusterRouting("rebalance", "enable", "all"), ["cluster"]
        )
    client.cluster.put_settings.assert_not_called()
    mock_relocate.assert_not_called()
    assert wb.status == "COMPLETED"
