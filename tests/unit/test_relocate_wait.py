"""Tests for Relocate waiter selected/all modes."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from es_tools.checkpoint.action_run import ActionRun, ExecuteResult, Mode
from es_tools.checkpoint.event_bus import EventBus
from es_tools.checkpoint.step import Step
from es_tools.wait.relocate import Relocate


def _state_client(routing_table: dict[str, Any]) -> MagicMock:
    """Mock client whose cluster.state() returns a routing table."""
    client = MagicMock()
    client.cluster.state.return_value = {
        "routing_table": {"indices": routing_table},
    }
    return client


def _health_client(relocating_shards: int) -> MagicMock:
    """Mock client whose cluster.health() reports relocating_shards."""
    client = MagicMock()
    client.cluster.health.return_value = {"relocating_shards": relocating_shards}
    return client


def test_selected_mode_returns_true_when_no_relocating_in_selected() -> None:
    """selected mode: True when selected indices have no RELOCATING shards."""
    routing = {
        "my-index": {
            "shards": {
                "0": [{"state": "STARTED", "node": "n1"}],
            }
        },
        "other-index": {
            "shards": {
                "0": [{"state": "RELOCATING", "node": "n2"}],
            }
        },
    }
    w = Relocate(_state_client(routing), indices=["my-index"], mode="selected")
    assert w.check() is True


def test_selected_mode_returns_false_when_selected_still_relocating() -> None:
    """selected mode: False when a selected index still has RELOCATING shards."""
    routing = {
        "my-index": {
            "shards": {
                "0": [{"state": "RELOCATING", "node": "n1"}],
            }
        },
    }
    w = Relocate(_state_client(routing), indices=["my-index"], mode="selected")
    assert w.check() is False


def test_all_mode_returns_true_when_zero_relocating() -> None:
    """all mode: True when cluster.health relocating_shards == 0."""
    w = Relocate(_health_client(0), indices=[], mode="all")
    assert w.check() is True


def test_all_mode_returns_false_when_relocating() -> None:
    """all mode: False when cluster.health relocating_shards > 0."""
    w = Relocate(_health_client(3), indices=[], mode="all")
    assert w.check() is False


def test_selected_mode_exception_counts_once() -> None:
    """Selected-mode state polling failures increment the counter once."""
    client = MagicMock()
    client.cluster.state.side_effect = RuntimeError("down")
    waiter = Relocate(client, indices=["my-index"], mode="selected")
    assert waiter.check() is False
    assert waiter.exceptions_raised == 1
    assert len(waiter._exceptions) == 1


def test_all_mode_exception_counts_once() -> None:
    """All-mode health polling failures increment the counter once."""
    client = MagicMock()
    client.cluster.health.side_effect = RuntimeError("down")
    waiter = Relocate(client, indices=[], mode="all")
    assert waiter.check() is False
    assert waiter.exceptions_raised == 1
    assert len(waiter._exceptions) == 1


def test_default_mode_is_selected() -> None:
    """Default mode is 'selected' (backward compatible)."""
    w = Relocate(_state_client({}), indices=["x"])
    assert w.mode == "selected"


def test_selected_mode_with_no_indices_in_routing_table() -> None:
    """selected mode: False when selected indices are absent from routing table."""
    routing = {"other": {"shards": {"0": [{"state": "STARTED"}]}}}
    w = Relocate(_state_client(routing), indices=["my-index"], mode="selected")
    assert w.check() is False


def test_selected_unassigned_is_not_done() -> None:
    """UNASSIGNED shards are not settled."""
    routing = {"my-index": {"shards": {"0": [{"state": "UNASSIGNED"}]}}}
    w = Relocate(_state_client(routing), indices=["my-index"], mode="selected")
    assert w.check() is False


def test_selected_started_is_done() -> None:
    """STARTED copies with no node pin are settled."""
    routing = {"my-index": {"shards": {"0": [{"state": "STARTED", "node": "n1"}]}}}
    w = Relocate(_state_client(routing), indices=["my-index"], mode="selected")
    assert w.check() is True


def test_selected_node_requires_target() -> None:
    """When node= is set, STARTED on the wrong node is not done."""
    routing = {"my-index": {"shards": {"0": [{"state": "STARTED", "node": "other"}]}}}
    w = Relocate(
        _state_client(routing),
        indices=["my-index"],
        mode="selected",
        node="es-data-1",
    )
    assert w.check() is False


def test_selected_node_ok_when_all_on_target() -> None:
    """All copies STARTED on the target node is done."""
    routing = {
        "my-index": {
            "shards": {
                "0": [
                    {"state": "STARTED", "node": "es-data-1"},
                    {"state": "STARTED", "node": "es-data-1"},
                ]
            }
        }
    }
    w = Relocate(_state_client(routing), indices=["my-index"], node="es-data-1")
    assert w.check() is True


def test_invalid_mode_raises() -> None:
    """mode must be selected or all."""
    with pytest.raises(ValueError, match="mode"):
        Relocate(MagicMock(), indices=["x"], mode="partial")


class _WaitRelocate:
    """whole_list dummy with relocate wait."""

    name = "waitrel"
    mode: Mode = "whole_list"
    wait_type: str | None = "relocate"

    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        return ExecuteResult(ok=True, names=names)


def test_action_run_passes_wait_mode_to_relocate() -> None:
    """ActionRun forwards wait_mode to Relocate."""
    client = MagicMock()
    mock_cls = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("es_tools.wait.relocate.Relocate", mock_cls)
        ActionRun(client, EventBus(), "es-checkpoint").run(
            _WaitRelocate(),
            ["cluster"],
            wait_mode="all",
        )
    mock_cls.assert_called_once()
    assert mock_cls.call_args.kwargs["mode"] == "all"
    assert mock_cls.call_args.kwargs["indices"] == ["cluster"]


def _step(client: MagicMock) -> Step:
    """Build a relocate-check Step."""
    return Step(
        EventBus(),
        "es-checkpoint",
        "s1",
        "job1",
        1,
        "wait-relocate",
        client,
        check_type="relocate",
        check_value="settled",
    )


def test_step_relocate_true_when_health_zero() -> None:
    """Step relocate check uses cluster.health relocating_shards == 0."""
    client = _health_client(0)
    assert _step(client)._check_state() is True
    client.cluster.health.assert_called()
    client.cluster.state.assert_not_called()


def test_step_relocate_false_when_health_nonzero() -> None:
    """Step relocate check is False while shards are relocating."""
    client = _health_client(2)
    assert _step(client)._check_state() is False
