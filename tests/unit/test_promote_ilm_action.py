"""Tests for PromoteIlm (advance one ILM phase)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from es_tools.checkpoint.action_run import ActionRun
from es_tools.checkpoint.event_bus import EventBus
from es_tools.index.actions.promote_ilm import PromoteIlm


def _explain(
    index: str,
    phase: str,
    *,
    managed: bool = True,
    action: str = "complete",
    step: str = "complete",
) -> dict:
    return {
        "indices": {
            index: {
                "managed": managed,
                "phase": phase,
                "action": action,
                "step": step,
            }
        }
    }


def test_promote_hot_moves_to_warm() -> None:
    """hot → warm via move_to_step, then wait warm complete."""
    client = MagicMock()
    client.ilm.explain_lifecycle.return_value = _explain("logs-1", "hot")
    with patch("es_tools.index.actions.promote_ilm.IlmPhase") as phase_w, patch(
        "es_tools.index.actions.promote_ilm.IlmStep"
    ) as step_w:
        phase_w.return_value.wait.return_value = True
        step_w.return_value.wait.return_value = True
        wb = ActionRun(client, EventBus(), "es-checkpoint").run(
            PromoteIlm(), ["logs-1"]
        )
    client.ilm.move_to_step.assert_called_once_with(
        index="logs-1",
        current_step={"phase": "hot", "action": "complete", "name": "complete"},
        next_step={"phase": "warm", "action": "complete", "name": "complete"},
    )
    assert wb.status == "COMPLETED"
    assert [s.name for s in wb.jobs[0].steps] == [
        "inspect-1",
        "move-1",
        "wait-target-1",
    ]


def test_promote_delete_skips_move() -> None:
    """Already last phase does not call move_to_step."""
    client = MagicMock()
    client.ilm.explain_lifecycle.return_value = _explain("old-1", "delete")
    with patch("es_tools.index.actions.promote_ilm.IlmPhase") as phase_w, patch(
        "es_tools.index.actions.promote_ilm.IlmStep"
    ) as step_w:
        phase_w.return_value.wait.return_value = True
        step_w.return_value.wait.return_value = True
        wb = ActionRun(client, EventBus(), "es-checkpoint").run(
            PromoteIlm(), ["old-1"]
        )
    client.ilm.move_to_step.assert_not_called()
    assert wb.status == "COMPLETED"


def test_promote_unmanaged_fails_step() -> None:
    """Unmanaged index fails the inspect Step (require_managed)."""
    client = MagicMock()
    client.ilm.explain_lifecycle.return_value = _explain(
        "bare-1", "hot", managed=False
    )
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(
        PromoteIlm(), ["bare-1"]
    )
    client.ilm.move_to_step.assert_not_called()
    assert wb.failures
    assert wb.jobs[0].status == "FAILED"


def test_promote_skips_write_backing_index() -> None:
    """Live data-stream write index is not moved."""
    index = ".ds-logs-000002"
    client = MagicMock()
    client.ilm.explain_lifecycle.return_value = _explain(index, "hot")
    client.indices.get.return_value = {index: {"data_stream": "logs"}}
    client.indices.get_data_stream.return_value = {
        "data_streams": [
            {
                "name": "logs",
                "indices": [
                    {"index_name": ".ds-logs-000001"},
                    {"index_name": index},
                ],
            }
        ]
    }
    with patch("es_tools.index.actions.promote_ilm.IlmPhase") as phase_w, patch(
        "es_tools.index.actions.promote_ilm.IlmStep"
    ) as step_w:
        wb = ActionRun(client, EventBus(), "es-checkpoint").run(
            PromoteIlm(), [index]
        )
    client.ilm.move_to_step.assert_not_called()
    phase_w.assert_not_called()
    step_w.assert_not_called()
    assert wb.status == "COMPLETED"


def test_promote_older_backing_still_moves() -> None:
    """Non-write backing index still advances one phase."""
    index = ".ds-logs-000001"
    client = MagicMock()
    client.ilm.explain_lifecycle.return_value = _explain(index, "hot")
    client.indices.get.return_value = {index: {"data_stream": "logs"}}
    client.indices.get_data_stream.return_value = {
        "data_streams": [
            {
                "name": "logs",
                "indices": [
                    {"index_name": index},
                    {"index_name": ".ds-logs-000002"},
                ],
            }
        ]
    }
    with patch("es_tools.index.actions.promote_ilm.IlmPhase") as phase_w, patch(
        "es_tools.index.actions.promote_ilm.IlmStep"
    ) as step_w:
        phase_w.return_value.wait.return_value = True
        step_w.return_value.wait.return_value = True
        wb = ActionRun(client, EventBus(), "es-checkpoint").run(
            PromoteIlm(), [index]
        )
    client.ilm.move_to_step.assert_called_once()
    assert wb.status == "COMPLETED"
