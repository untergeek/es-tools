"""Tests for index list actions."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from es_tools.checkpoint.action_run import ActionRun
from es_tools.checkpoint.event_bus import EventBus
from es_tools.index.actions import (
    CloseIndices,
    DeleteIndices,
    ForceMerge,
    OpenIndices,
    PutIndexSettings,
    SetAllocation,
    SetReplicas,
)


def _run(action, names, **opts):
    client = MagicMock()
    client.indices.exists.return_value = False
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(action, names, **opts)
    return client, wb


def test_open_one_job_csv_call() -> None:
    """Open sends a single CSV URI for a small list."""
    client, wb = _run(OpenIndices(), ["a", "b"])
    client.indices.open.assert_called_once_with(index="a,b", ignore_unavailable=True)
    assert len(wb.jobs) == 1
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1"]
    assert wb.status == "COMPLETED"


def test_close_default_flushes_then_closes() -> None:
    """Default close flushes then closes and does not delete aliases."""
    client, wb = _run(CloseIndices(), ["a"])
    client.indices.flush.assert_called_once()
    client.indices.close.assert_called_once_with(index="a", ignore_unavailable=True)
    client.indices.delete_alias.assert_not_called()
    assert [s.name for s in wb.jobs[0].steps] == ["close-1"]


def test_close_skip_flush() -> None:
    """skip_flush=True skips the flush call."""
    client, _wb = _run(CloseIndices(), ["a"], skip_flush=True)
    client.indices.flush.assert_not_called()
    client.indices.close.assert_called_once()


def test_close_delete_aliases_extra_step() -> None:
    """delete_aliases=True adds a delete-aliases Step before close."""
    client, wb = _run(CloseIndices(), ["a"], delete_aliases=True)
    client.indices.delete_alias.assert_called_once_with(index="a", name="*")
    assert [s.name for s in wb.jobs[0].steps] == ["delete-aliases-1", "close-1"]


def test_close_delete_alias_failure_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """delete_alias errors are logged; close still runs."""
    client = MagicMock()
    client.indices.delete_alias.side_effect = RuntimeError("no alias")
    with caplog.at_level(logging.WARNING):
        wb = ActionRun(client, EventBus(), "es-checkpoint").run(
            CloseIndices(), ["a"], delete_aliases=True
        )
    client.indices.close.assert_called_once()
    assert wb.status == "COMPLETED"
    assert any("delete_alias" in r.message for r in caplog.records)


def test_close_dry_run_delete_aliases_emits_step_without_es() -> None:
    """dry_run + delete_aliases emits the pre-step and does not call ES."""
    client = MagicMock()
    wb = ActionRun(client, EventBus(), "es-checkpoint", dry_run=True).run(
        CloseIndices(), ["a"], delete_aliases=True
    )
    client.indices.delete_alias.assert_not_called()
    client.indices.close.assert_not_called()
    assert [s.name for s in wb.jobs[0].steps] == ["delete-aliases-1", "close-1"]


def test_delete_retries_then_succeeds() -> None:
    """Delete retries while exists() is True, then succeeds."""
    client = MagicMock()
    client.indices.exists.side_effect = [True, False]
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(DeleteIndices(), ["gone"])
    assert client.indices.delete.call_count == 2
    assert wb.status == "COMPLETED"


def test_delete_transport_error_fails_immediately() -> None:
    """A client exception on delete is not retried."""
    client = MagicMock()
    client.indices.delete.side_effect = RuntimeError("timeout")
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(DeleteIndices(), ["stuck"])
    assert client.indices.delete.call_count == 1
    client.indices.exists.assert_not_called()
    assert wb.jobs[0].steps[0].status == "FAILED"
    assert wb.status == "CANCELLED"


def test_put_settings_requires_body() -> None:
    """Empty settings are rejected at construction."""
    with pytest.raises(ValueError, match="settings"):
        PutIndexSettings({})


def test_put_settings_calls_client() -> None:
    """put_settings receives the CSV and settings body."""
    settings = {"index": {"refresh_interval": "-1"}}
    client, _wb = _run(PutIndexSettings(settings), ["a", "b"])
    client.indices.put_settings.assert_called_once_with(index="a,b", settings=settings)


def test_replicas_zero_does_not_wait() -> None:
    """count=0 has no relocate wait Step."""
    _client, wb = _run(SetReplicas(0), ["a"])
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1"]


def test_replicas_positive_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    """count>0 adds a wait Step that constructs Relocate."""
    mock_cls = MagicMock()
    monkeypatch.setattr("es_tools.wait.relocate.Relocate", mock_cls)
    _client, wb = _run(SetReplicas(1), ["a"], wait_for_completion=True)
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1", "wait-1"]
    mock_cls.assert_called_once()
    mock_cls.return_value.wait.assert_called_once()


def test_allocation_requires_key() -> None:
    """Allocation without a key fails."""
    with pytest.raises(ValueError, match="key"):
        SetAllocation(key="")


def test_allocation_setting_key() -> None:
    """Allocation writes the routing setting."""
    client, _wb = _run(
        SetAllocation(key="tag", value="hot"),
        ["a"],
        wait_for_completion=False,
    )
    client.indices.put_settings.assert_called_once()
    body = client.indices.put_settings.call_args.kwargs["settings"]
    assert "index.routing.allocation.require.tag" in body


def test_forcemerge_one_step_per_index() -> None:
    """Force-merge is per-item under one Job."""
    client, wb = _run(ForceMerge(1), ["a", "b"])
    assert client.indices.forcemerge.call_count == 2
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1", "execute-2"]
    assert len(wb.jobs) == 1


def test_forcemerge_rejects_bad_segments() -> None:
    """max_num_segments must be >= 1."""
    with pytest.raises(ValueError, match="max_num_segments"):
        ForceMerge(0)
