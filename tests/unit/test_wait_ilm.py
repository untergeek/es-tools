"""Tests for ILM waiters (explain_lifecycle + indices{} shape)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from es_tools.checkpoint.action_run import ActionRun, ExecuteResult, Mode
from es_tools.checkpoint.event_bus import EventBus
from es_tools.exceptions import ESToolActionError, ESToolIlmWaitError
from es_tools.wait.ilm import IlmPhase, IlmStep


def test_ilm_phase_true_when_phase_matches() -> None:
    """IlmPhase is done when indices[index].phase matches."""
    client = MagicMock()
    client.ilm.explain_lifecycle.return_value = {
        "indices": {"idx": {"managed": True, "phase": "cold", "step": "complete"}}
    }
    assert IlmPhase(client, index="idx", phase="cold").check() is True
    client.ilm.explain_lifecycle.assert_called_with(index="idx")


def test_ilm_phase_false_when_still_hot() -> None:
    """IlmPhase keeps waiting while the index is still in another phase."""
    client = MagicMock()
    client.ilm.explain_lifecycle.return_value = {
        "indices": {"idx": {"managed": True, "phase": "hot", "step": "rollover"}}
    }
    assert IlmPhase(client, index="idx", phase="cold").check() is False


def test_ilm_phase_raises_if_unmanaged() -> None:
    """Unmanaged indices are fatal, not a timeout."""
    client = MagicMock()
    client.ilm.explain_lifecycle.return_value = {"indices": {"idx": {"managed": False}}}
    with pytest.raises(ESToolIlmWaitError, match="not managed"):
        IlmPhase(client, index="idx", phase="cold").check()


def test_ilm_phase_exception_counts_once() -> None:
    """Non-ILM exceptions increment the counter once and remain retryable."""
    client = MagicMock()
    client.ilm.explain_lifecycle.side_effect = RuntimeError("down")
    waiter = IlmPhase(client, index="idx", phase="cold")
    assert waiter.check() is False
    assert waiter.exceptions_raised == 1
    assert len(waiter._exceptions) == 1


def test_ilm_phase_new_accepts_later_phase() -> None:
    """phase='new' is done when the index is already past new (es_wait 0.9.2)."""
    client = MagicMock()
    client.ilm.explain_lifecycle.return_value = {
        "indices": {"idx": {"managed": True, "phase": "frozen", "step": "complete"}}
    }
    assert IlmPhase(client, index="idx", phase="new").check() is True


def test_ilm_phase_cold_accepts_frozen() -> None:
    """Any target phase is done at that phase or later."""
    client = MagicMock()
    client.ilm.explain_lifecycle.return_value = {
        "indices": {"idx": {"managed": True, "phase": "frozen", "step": "complete"}}
    }
    assert IlmPhase(client, index="idx", phase="cold").check() is True


def test_ilm_phase_rejects_unknown_target() -> None:
    """Ctor rejects phases outside the ILM order."""
    with pytest.raises(ValueError, match="phase"):
        IlmPhase(MagicMock(), index="idx", phase="complete")


def test_ilm_step_uses_step_field() -> None:
    """IlmStep compares the explain `step` field."""
    client = MagicMock()
    client.ilm.explain_lifecycle.return_value = {
        "indices": {"idx": {"managed": True, "phase": "cold", "step": "complete"}}
    }
    assert IlmStep(client, index="idx", step="complete").check() is True


def test_ilm_step_exception_counts_once() -> None:
    """Non-ILM exceptions increment the counter once and remain retryable."""
    client = MagicMock()
    client.ilm.explain_lifecycle.side_effect = RuntimeError("down")
    waiter = IlmStep(client, index="idx", step="complete")
    assert waiter.check() is False
    assert waiter.exceptions_raised == 1
    assert len(waiter._exceptions) == 1


def test_does_not_call_explain() -> None:
    """elasticsearch9 has no ilm.explain; waiters must not call it."""
    client = MagicMock()
    client.ilm.explain_lifecycle.return_value = {
        "indices": {"idx": {"managed": True, "phase": "cold", "step": "complete"}}
    }
    IlmPhase(client, "idx", "cold").check()
    client.ilm.explain.assert_not_called()


class _WaitIlm:
    """per_item dummy with ilm_phase wait."""

    name = "waitilm"
    mode: Mode = "per_item"
    wait_type: str | None = "ilm_phase"
    ilm_phase = "cold"

    def execute(
        self, client: object, names: list[str], **opts: object
    ) -> ExecuteResult:
        return ExecuteResult(ok=True, names=names)


class _WaitIlmOpts:
    """per_item dummy that relies on opts['phase']."""

    name = "waitilmopts"
    mode: Mode = "per_item"
    wait_type: str | None = "ilm_phase"

    def execute(
        self, client: object, names: list[str], **opts: object
    ) -> ExecuteResult:
        return ExecuteResult(ok=True, names=names)


class _WaitIlmStep:
    """per_item dummy with ilm_step wait."""

    name = "waitilmstep"
    mode: Mode = "per_item"
    wait_type: str | None = "ilm_step"

    def execute(
        self, client: object, names: list[str], **opts: object
    ) -> ExecuteResult:
        return ExecuteResult(ok=True, names=names)


class _WaitIlmWhole:
    """whole_list dummy with ilm_phase wait (must reject multiple names)."""

    name = "waitilmwhole"
    mode: Mode = "whole_list"
    wait_type: str | None = "ilm_phase"
    ilm_phase = "cold"

    def execute(
        self, client: object, names: list[str], **opts: object
    ) -> ExecuteResult:
        return ExecuteResult(ok=True, names=names)


def test_action_run_ilm_phase_waiter() -> None:
    """ActionRun forwards index + action.ilm_phase to IlmPhase."""
    client = MagicMock()
    mock_cls = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("es_tools.wait.ilm.IlmPhase", mock_cls)
        ActionRun(client, EventBus(), "es-checkpoint").run(_WaitIlm(), ["logs-1"])
    mock_cls.assert_called_once()
    assert mock_cls.call_args.kwargs["index"] == "logs-1"
    assert mock_cls.call_args.kwargs["phase"] == "cold"
    mock_cls.return_value.wait.assert_called_once()


def test_action_run_ilm_phase_from_opts() -> None:
    """opts['phase'] supplies the target phase when the action has none."""
    client = MagicMock()
    mock_cls = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("es_tools.wait.ilm.IlmPhase", mock_cls)
        ActionRun(client, EventBus(), "es-checkpoint").run(
            _WaitIlmOpts(), ["logs-1"], phase="frozen"
        )
    assert mock_cls.call_args.kwargs["phase"] == "frozen"
    assert mock_cls.call_args.kwargs["index"] == "logs-1"


def test_action_run_ilm_phase_missing_phase_raises() -> None:
    """ilm_phase wait without phase is ESToolActionError."""
    run = ActionRun(MagicMock(), EventBus(), "es-checkpoint")
    with pytest.raises(ESToolActionError, match="requires phase"):
        run._wait_type(
            "ilm_phase",
            ExecuteResult(ok=True, names=["logs-1"]),
            ["logs-1"],
            {},
            _WaitIlmOpts(),
        )


def test_action_run_ilm_step_defaults_to_complete() -> None:
    """ilm_step wait uses step complete when none is set."""
    client = MagicMock()
    mock_cls = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("es_tools.wait.ilm.IlmStep", mock_cls)
        ActionRun(client, EventBus(), "es-checkpoint").run(_WaitIlmStep(), ["logs-1"])
    mock_cls.assert_called_once()
    assert mock_cls.call_args.kwargs["index"] == "logs-1"
    assert mock_cls.call_args.kwargs["step"] == "complete"
    mock_cls.return_value.wait.assert_called_once()


def test_action_run_ilm_wait_rejects_multiple_names() -> None:
    """ILM wait requires a single index name."""
    run = ActionRun(MagicMock(), EventBus(), "es-checkpoint")
    with pytest.raises(ESToolActionError, match="single index"):
        run._wait_type(
            "ilm_phase",
            ExecuteResult(ok=True, names=["a", "b"]),
            ["a", "b"],
            {},
            _WaitIlmWhole(),
        )


def test_wait_type_unknown_raises() -> None:
    """Unknown wait_type is ESToolActionError."""
    run = ActionRun(MagicMock(), EventBus(), "es-checkpoint")
    with pytest.raises(ESToolActionError, match="unknown wait_type"):
        run._wait_type(
            "nope",
            ExecuteResult(ok=True, names=["logs-1"]),
            ["logs-1"],
            {},
            None,
        )
