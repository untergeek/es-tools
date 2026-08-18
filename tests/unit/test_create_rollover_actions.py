"""Tests for CreateIndices and RolloverIndices."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from es_tools.checkpoint.action_run import ActionRun
from es_tools.checkpoint.event_bus import EventBus
from es_tools.index.actions import CreateIndices, RolloverIndices


class _AlreadyExists(Exception):
    """Stand-in for elasticsearch9.BadRequestError."""

    error = "resource_already_exists_exception"


def _run(action, names, **opts):
    client = MagicMock()
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(action, names, **opts)
    return client, wb


def test_create_index_per_item() -> None:
    """Each name is its own indices.create Step."""
    client, wb = _run(
        CreateIndices(settings={"number_of_shards": 1}, mappings={"properties": {}}),
        ["a", "b"],
    )
    assert client.indices.create.call_count == 2
    client.indices.create.assert_any_call(
        index="a", settings={"number_of_shards": 1}, mappings={"properties": {}}
    )
    client.indices.create.assert_any_call(
        index="b", settings={"number_of_shards": 1}, mappings={"properties": {}}
    )
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1", "execute-2"]
    assert wb.jobs[0].index == "create_index:2"
    assert wb.status == "COMPLETED"


def test_create_index_omits_none_kwargs() -> None:
    """Do not send aliases/mappings/settings when unset."""
    client, _wb = _run(CreateIndices(), ["only"])
    client.indices.create.assert_called_once_with(index="only")


def test_create_index_existing_fails_by_default() -> None:
    """resource_already_exists fails the Step when ignore_existing is False."""
    client = MagicMock()
    client.indices.create.side_effect = _AlreadyExists("exists")
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(CreateIndices(), ["a"])
    assert wb.jobs[0].steps[0].status == "FAILED"
    assert wb.status == "CANCELLED"


def test_create_index_ignore_existing() -> None:
    """ignore_existing treats resource_already_exists as success."""
    client = MagicMock()
    client.indices.create.side_effect = _AlreadyExists("exists")
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(
        CreateIndices(ignore_existing=True), ["a"]
    )
    assert wb.status == "COMPLETED"


def test_rollover_per_alias() -> None:
    """Each alias name is one indices.rollover Step."""
    conditions = {"max_age": "7d"}
    extra = {"number_of_shards": 1}
    client, wb = _run(
        RolloverIndices(
            conditions,
            new_index="logs-000002",
            extra_settings=extra,
            wait_for_active_shards=1,
        ),
        ["logs-write", "metrics-write"],
    )
    assert client.indices.rollover.call_count == 2
    client.indices.rollover.assert_any_call(
        alias="logs-write",
        new_index="logs-000002",
        conditions=conditions,
        settings=extra,
        wait_for_active_shards=1,
    )
    client.indices.rollover.assert_any_call(
        alias="metrics-write",
        new_index="logs-000002",
        conditions=conditions,
        settings=extra,
        wait_for_active_shards=1,
    )
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1", "execute-2"]
    assert wb.jobs[0].index == "rollover:2"
    assert wb.status == "COMPLETED"


def test_rollover_omits_optional_none() -> None:
    """Unset new_index/settings are not sent."""
    client, _wb = _run(RolloverIndices({"max_docs": 1000}), ["logs-write"])
    client.indices.rollover.assert_called_once_with(
        alias="logs-write",
        conditions={"max_docs": 1000},
        wait_for_active_shards=1,
    )


def test_rollover_not_rolled_over_is_completed() -> None:
    """ES 200 {rolled_over: false} is COMPLETED; raw is on workbook.results."""
    body = {"rolled_over": False, "new_index": "logs-000002"}
    client = MagicMock()
    client.indices.rollover.return_value = body
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(
        RolloverIndices({"max_docs": 1000}), ["logs-write"]
    )
    assert wb.status == "COMPLETED"
    assert wb.jobs[0].status == "COMPLETED"
    assert wb.results[0]["ok"] is True
    assert wb.results[0]["raw"] == body
    assert wb.results[0]["raw"]["rolled_over"] is False


def test_rollover_body_attr_raw_on_results() -> None:
    """Rollover raw with .body dict still exposes rolled_over on results."""
    body = {"rolled_over": False, "new_index": "logs-000002"}
    client = MagicMock()
    client.indices.rollover.return_value = SimpleNamespace(body=body)
    wb = ActionRun(client, EventBus(), "es-checkpoint").run(
        RolloverIndices({"max_docs": 1000}), ["logs-write"]
    )
    assert wb.status == "COMPLETED"
    assert wb.results[0]["raw"]["rolled_over"] is False
    assert wb.results[0]["raw"]["new_index"] == "logs-000002"
