"""Tests for ConfirmIlmPhase (move_to_step + new-or-later wait)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from es_tools.checkpoint.action_run import ActionRun
from es_tools.checkpoint.event_bus import EventBus
from es_tools.index.actions.confirm_ilm import ConfirmIlmPhase


def _explain(phase: str, action: str = "complete", step: str = "complete") -> dict:
    return {
        "indices": {
            "mounted": {
                "managed": True,
                "phase": phase,
                "action": action,
                "step": step,
            }
        }
    }


def test_confirm_rejects_empty_or_new_phase() -> None:
    """Target phase is a real lifecycle phase, not the 'new' sentinel."""
    with pytest.raises(ValueError, match="phase"):
        ConfirmIlmPhase("")
    with pytest.raises(ValueError, match="phase"):
        ConfirmIlmPhase("new")


def test_confirm_skips_move_when_already_at_target() -> None:
    """Already {cold, complete, complete} does not call move_to_step."""
    client = MagicMock()
    client.ilm.explain_lifecycle.return_value = _explain("cold")
    with patch("es_tools.index.actions.confirm_ilm.IlmPhase") as phase_w, patch(
        "es_tools.index.actions.confirm_ilm.IlmStep"
    ) as step_w:
        phase_w.return_value.wait.return_value = True
        step_w.return_value.wait.return_value = True
        wb = ActionRun(client, EventBus(), "es-checkpoint").run(
            ConfirmIlmPhase("cold"), ["mounted"]
        )
    client.ilm.move_to_step.assert_not_called()
    assert wb.status == "COMPLETED"
    assert [s.name for s in wb.jobs[0].steps] == [
        "wait-new-1",
        "move-1",
        "wait-target-1",
    ]


def test_confirm_moves_from_new_to_cold() -> None:
    """move_to_step current_step comes from explain; next is complete/complete."""
    client = MagicMock()
    client.ilm.explain_lifecycle.return_value = _explain(
        "new", action="complete", step="complete"
    )
    with patch("es_tools.index.actions.confirm_ilm.IlmPhase") as phase_w, patch(
        "es_tools.index.actions.confirm_ilm.IlmStep"
    ) as step_w:
        phase_w.return_value.wait.return_value = True
        step_w.return_value.wait.return_value = True
        ActionRun(client, EventBus(), "es-checkpoint").run(
            ConfirmIlmPhase("cold"), ["mounted"]
        )
    client.ilm.move_to_step.assert_called_once_with(
        index="mounted",
        current_step={"phase": "new", "action": "complete", "name": "complete"},
        next_step={"phase": "cold", "action": "complete", "name": "complete"},
    )


def test_confirm_retries_move_then_fails() -> None:
    """Three move_to_step failures become ESToolActionError."""
    client = MagicMock()
    client.ilm.explain_lifecycle.return_value = _explain("new")
    client.ilm.move_to_step.side_effect = RuntimeError("conflict")
    with patch("es_tools.index.actions.confirm_ilm.IlmPhase") as phase_w, patch(
        "es_tools.index.actions.confirm_ilm.IlmStep"
    ) as step_w, patch("es_tools.index.actions.confirm_ilm.sleep"):
        phase_w.return_value.wait.return_value = True
        step_w.return_value.wait.return_value = True
        wb = ActionRun(client, EventBus(), "es-checkpoint").run(
            ConfirmIlmPhase("cold"), ["mounted"]
        )
    assert client.ilm.move_to_step.call_count == 3
    assert wb.failures
    assert wb.jobs[0].status == "FAILED"
