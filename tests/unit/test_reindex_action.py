"""Tests for ReindexIndices and ActionRun task wait."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from es_tools.checkpoint.action_run import ActionRun
from es_tools.checkpoint.event_bus import EventBus
from es_tools.index.actions import ReindexIndices


def test_reindex_rejects_empty_dest() -> None:
    """dest must be a non-empty string."""
    with pytest.raises(ValueError, match="dest"):
        ReindexIndices("")


def test_reindex_starts_async_per_source() -> None:
    """Each source is one reindex call with wait_for_completion=False."""
    client = MagicMock()
    client.reindex.return_value = {"task": "node:1"}
    mock_task = MagicMock()
    action = ReindexIndices("dest-idx")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("es_tools.wait.task.Task", mock_task)
        wb = ActionRun(client, EventBus(), "es-checkpoint").run(
            action, ["src-a", "src-b"]
        )
    assert client.reindex.call_count == 2
    client.reindex.assert_any_call(
        source={"index": "src-a"},
        dest={"index": "dest-idx"},
        wait_for_completion=False,
    )
    client.reindex.assert_any_call(
        source={"index": "src-b"},
        dest={"index": "dest-idx"},
        wait_for_completion=False,
    )
    assert [s.name for s in wb.jobs[0].steps] == [
        "execute-1",
        "wait-1",
        "execute-2",
        "wait-2",
    ]
    assert wb.jobs[0].index == "reindex:2"
    assert mock_task.call_count == 2
    assert mock_task.call_args.kwargs["task_id"] == "node:1"
    assert mock_task.call_args.kwargs["action"] == "reindex"
    mock_task.return_value.wait.assert_called()
    assert wb.status == "COMPLETED"


def test_reindex_body_extra_merges() -> None:
    """body_extra is forwarded; source/dest index still come from names/ctor."""
    client = MagicMock()
    client.reindex.return_value = {"task": "t"}
    action = ReindexIndices(
        "dest-idx",
        body_extra={"conflicts": "proceed", "source": {"size": 500}},
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("es_tools.wait.task.Task", MagicMock())
        ActionRun(client, EventBus(), "es-checkpoint").run(action, ["src"])
    client.reindex.assert_called_once_with(
        source={"index": "src", "size": 500},
        dest={"index": "dest-idx"},
        wait_for_completion=False,
        conflicts="proceed",
    )


def test_reindex_skip_wait() -> None:
    """wait_for_completion=False skips the Task waiter."""
    client = MagicMock()
    client.reindex.return_value = {"task": "t"}
    mock_task = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("es_tools.wait.task.Task", mock_task)
        wb = ActionRun(client, EventBus(), "es-checkpoint").run(
            ReindexIndices("dest-idx"), ["src"], wait_for_completion=False
        )
    mock_task.assert_not_called()
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1"]
    assert wb.status == "COMPLETED"
