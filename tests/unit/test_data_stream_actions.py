"""Tests for DeleteDataStreams and RolloverDataStreams."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from elastic_transport import ApiResponseMeta, HttpHeaders
from elasticsearch9 import NotFoundError

from es_tools.checkpoint.action_run import ActionRun
from es_tools.checkpoint.event_bus import EventBus
from es_tools.index.actions import DeleteDataStreams, RolloverDataStreams


def _not_found() -> NotFoundError:
    meta = ApiResponseMeta(
        status=404,
        http_version="1.1",
        headers=HttpHeaders(),
        duration=0.0,
        node=None,  # type: ignore[arg-type]
    )
    return NotFoundError(
        "not found", meta, {"error": {"type": "resource_not_found_exception"}}
    )


def _run(action: Any, names: list[str], **opts: Any) -> tuple[Any, Any]:
    client = MagicMock()
    client.indices.get_data_stream.side_effect = _not_found()
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(action, names, **opts)
    return client, wb


def test_delete_data_streams_csv_chunk() -> None:
    """Delete sends comma-separated stream names in the URI."""
    client, wb = _run(DeleteDataStreams(), ["logs-nginx", "logs-system"])
    client.indices.delete_data_stream.assert_called_once_with(
        name="logs-nginx,logs-system"
    )
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1"]
    assert wb.status == "COMPLETED"


def test_delete_data_streams_retries_while_present() -> None:
    """Retry while get_data_stream still returns the stream."""
    client = MagicMock()
    client.indices.get_data_stream.side_effect = [
        {"data_streams": [{"name": "logs"}]},
        _not_found(),
    ]
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(
        DeleteDataStreams(), ["logs"]
    )
    assert client.indices.delete_data_stream.call_count == 2
    assert wb.status == "COMPLETED"


def test_delete_data_streams_transport_error_fails_immediately() -> None:
    """A client exception on delete is not retried."""
    client = MagicMock()
    client.indices.delete_data_stream.side_effect = RuntimeError("timeout")
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(
        DeleteDataStreams(), ["stuck"]
    )
    assert client.indices.delete_data_stream.call_count == 1
    client.indices.get_data_stream.assert_not_called()
    assert wb.jobs[0].steps[0].status == "FAILED"
    assert wb.status == "CANCELLED"


def test_delete_data_streams_already_gone_is_ok() -> None:
    """404 on delete is success when the stream is already absent."""
    client = MagicMock()
    client.indices.delete_data_stream.side_effect = _not_found()
    client.indices.get_data_stream.side_effect = _not_found()
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(
        DeleteDataStreams(), ["gone"]
    )
    assert wb.status == "COMPLETED"


def test_rollover_data_stream_per_item() -> None:
    """Each stream name is one indices.rollover Step. No new_index."""
    conditions = {"max_age": "7d"}
    client, wb = _run(
        RolloverDataStreams(conditions, wait_for_active_shards=1),
        ["logs-nginx", "logs-system"],
    )
    assert client.indices.rollover.call_count == 2
    client.indices.rollover.assert_any_call(
        alias="logs-nginx",
        conditions=conditions,
        wait_for_active_shards=1,
    )
    client.indices.rollover.assert_any_call(
        alias="logs-system",
        conditions=conditions,
        wait_for_active_shards=1,
    )
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1", "execute-2"]
    assert wb.jobs[0].index == "rollover_data_streams:2"
    assert wb.status == "COMPLETED"


def test_rollover_data_stream_unconditional() -> None:
    """Empty conditions are omitted (unconditional rollover)."""
    client, _wb = _run(RolloverDataStreams({}), ["logs-nginx"])
    client.indices.rollover.assert_called_once_with(
        alias="logs-nginx",
        wait_for_active_shards=1,
    )
