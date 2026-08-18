"""Tests for RedactIlm orchestrator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from es_tools.checkpoint.event_bus import EventBus
from es_tools.redact.ilm import RedactIlm


def test_redact_ilm_unmanaged_is_noop() -> None:
    """Unmanaged source skips apply and confirm."""
    client = MagicMock()
    client.indices.get_settings.return_value = {"src": {"settings": {"index": {}}}}
    assert RedactIlm(client, EventBus(), "es-checkpoint").run("src", "mounted") is None
    client.indices.put_settings.assert_not_called()
    client.ilm.move_to_step.assert_not_called()


def test_redact_ilm_apply_then_confirm() -> None:
    """Clone result drives ApplyIlmPolicy then ConfirmIlmPhase on mounted."""
    cloned = MagicMock()
    cloned.lifecycle = {"name": "es-tools-logs---v001"}
    cloned.phase = "cold"
    cloned.name = "es-tools-logs---v001"
    client = MagicMock()
    with patch("es_tools.redact.ilm.clone_ilm_policy", return_value=cloned), patch(
        "es_tools.redact.ilm.ActionRun"
    ) as run_cls:
        run_cls.return_value.run.return_value = MagicMock()
        RedactIlm(client, EventBus(), "es-checkpoint").run("src", "mounted")
    assert run_cls.return_value.run.call_count == 2
    apply_action = run_cls.return_value.run.call_args_list[0].args[0]
    confirm_action = run_cls.return_value.run.call_args_list[1].args[0]
    assert apply_action.lifecycle["name"] == "es-tools-logs---v001"
    assert confirm_action.phase == "cold"
    assert run_cls.return_value.run.call_args_list[0].args[1] == ["mounted"]
    assert run_cls.return_value.run.call_args_list[1].args[1] == ["mounted"]
