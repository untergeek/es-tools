"""Tests for RedactFields (real update_by_query, not a stub)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from es_tools.checkpoint.action_run import ActionRun, ExecuteResult
from es_tools.checkpoint.event_bus import EventBus
from es_tools.redact.fields import RedactFields, build_script, count_hits
from es_tools.wait.dispatch import wait_on


def _hits(n: int) -> dict:
    return {"hits": {"total": {"value": n}}}


def test_build_script_sets_fields() -> None:
    script = build_script("REDACTED", ["ssn", "user.email"])
    assert script["lang"] == "painless"
    assert script["params"]["replacement"] == "REDACTED"
    assert "ctx._source.ssn" in script["source"]
    assert "ctx._source.user.email" in script["source"]


def test_redact_fields_starts_update_by_query() -> None:
    client = MagicMock()
    client.search.side_effect = [_hits(2), _hits(0)]
    client.update_by_query.return_value = {"task": "abc:123"}
    action = RedactFields(
        query={"term": {"ssn": "1"}},
        fields=["ssn"],
        message="REDACTED",
    )
    with patch("es_tools.redact.fields.Task") as task_cls:
        task_cls.return_value.wait.return_value = True
        result = action.execute(client, ["logs-1"])
    assert result.ok
    assert result.task_id == "abc:123"
    client.update_by_query.assert_called_once()
    kwargs = client.update_by_query.call_args.kwargs
    assert kwargs["index"] == "logs-1"
    assert kwargs["wait_for_completion"] is False
    assert kwargs["query"] == {"term": {"ssn": "1"}}
    assert kwargs["script"]["params"]["replacement"] == "REDACTED"
    assert "ctx._source.ssn" in kwargs["script"]["source"]


def test_redact_fields_dry_run_does_not_call_es() -> None:
    client = MagicMock()
    wb = ActionRun(client, EventBus(), "es-steward-journal", dry_run=True).run(
        RedactFields(query={"match_all": {}}, fields=["ssn"], message="X"),
        ["logs-1"],
    )
    client.update_by_query.assert_not_called()
    client.search.assert_not_called()
    assert wb.status == "COMPLETED"


def test_redact_fields_rejects_empty() -> None:
    with pytest.raises(ValueError, match="query"):
        RedactFields(query={}, fields=["ssn"], message="X")
    with pytest.raises(ValueError, match="fields"):
        RedactFields(query={"match_all": {}}, fields=[], message="X")
    with pytest.raises(ValueError, match="fields"):
        RedactFields(query={"match_all": {}}, fields=[""], message="X")
    with pytest.raises(ValueError, match="fields"):
        RedactFields(query={"match_all": {}}, fields=["user."], message="X")
    with pytest.raises(ValueError, match="message"):
        RedactFields(query={"match_all": {}}, fields=["ssn"], message="")
    with pytest.raises(ValueError, match="message"):
        build_script("", ["ssn"])
    with pytest.raises(ValueError, match="fields"):
        build_script("X", [])


def test_wait_task_uses_update_by_query_action() -> None:
    client = MagicMock()
    result = ExecuteResult(ok=True, names=["logs-1"], task_id="abc:123")
    action = RedactFields(query={"match_all": {}}, fields=["ssn"], message="X")
    with patch("es_tools.wait.dispatch.wait_task.Task") as task_cls:
        task_cls.return_value.wait.return_value = True
        wait_on("task", client, result, ["logs-1"], {}, action)
        assert task_cls.call_args.kwargs["action"] == "update_by_query"
        assert task_cls.call_args.kwargs["task_id"] == "abc:123"


def test_missing_task_id_fails_execute() -> None:
    client = MagicMock()
    client.search.return_value = _hits(1)
    client.update_by_query.return_value = {}
    result = RedactFields(
        query={"match_all": {}}, fields=["ssn"], message="X"
    ).execute(client, ["logs-1"])
    assert result.ok is False
    assert result.task_id is None
    assert result.error


def test_zero_hits_does_not_call_update_by_query() -> None:
    client = MagicMock()
    client.search.return_value = _hits(0)
    result = RedactFields(
        query={"match_all": {}}, fields=["ssn"], message="X"
    ).execute(client, ["logs-1"])
    assert result.ok
    client.update_by_query.assert_not_called()


def test_remaining_hits_fail_execute() -> None:
    client = MagicMock()
    client.search.return_value = _hits(3)
    client.update_by_query.return_value = {"task": "t:1"}
    action = RedactFields(query={"match_all": {}}, fields=["ssn"], message="X")
    with patch("es_tools.redact.fields.Task") as task_cls:
        task_cls.return_value.wait.return_value = True
        result = action.execute(client, ["logs-1"])
    assert result.ok is False
    assert "hits remain" in (result.error or "")
    assert client.update_by_query.call_count == 11


def test_remaining_hits_do_not_complete_workbook() -> None:
    client = MagicMock()
    client.search.return_value = _hits(1)
    client.update_by_query.return_value = {"task": "t:1"}
    action = RedactFields(query={"match_all": {}}, fields=["ssn"], message="X")
    with patch("es_tools.redact.fields.Task") as task_cls:
        task_cls.return_value.wait.return_value = True
        wb = ActionRun(client, EventBus(), "es-steward-journal").run(
            action, ["logs-1"]
        )
    assert wb.status != "COMPLETED"


def test_count_hits_reads_total_value() -> None:
    client = MagicMock()
    client.search.return_value = _hits(7)
    assert count_hits(client, "logs-1", {"match_all": {}}) == 7
    kwargs = client.search.call_args.kwargs
    assert kwargs["size"] == 0
    assert kwargs["track_total_hits"] is True


def test_count_hits_reads_es7_int_total() -> None:
    client = MagicMock()
    client.search.return_value = {"hits": {"total": 4}}
    assert count_hits(client, "logs-1", {"match_all": {}}) == 4


def test_count_hits_raises_on_unrecognizable_body() -> None:
    from es_tools.exceptions import ESToolActionError

    client = MagicMock()
    client.search.return_value = {"took": 1}
    with pytest.raises(ESToolActionError, match="hits"):
        count_hits(client, "logs-1", {"match_all": {}})
    client.search.return_value = object()
    with pytest.raises(ESToolActionError, match="mapping"):
        count_hits(client, "logs-1", {"match_all": {}})


def test_unrecognizable_search_does_not_complete_workbook() -> None:
    client = MagicMock()
    client.search.return_value = {"error": "nope"}
    wb = ActionRun(client, EventBus(), "es-steward-journal").run(
        RedactFields(query={"match_all": {}}, fields=["ssn"], message="X"),
        ["logs-1"],
    )
    client.update_by_query.assert_not_called()
    assert wb.status != "COMPLETED"


def test_redact_fields_publishes_progress() -> None:
    """Each update_by_query round publishes Progress when a bus is passed."""
    from es_tools.checkpoint.events import Progress

    client = MagicMock()
    client.search.side_effect = [_hits(5), _hits(2), _hits(0)]
    client.update_by_query.return_value = {"task": "abc:123"}
    bus = EventBus()
    seen: list[Progress] = []
    bus.subscribe(Progress, seen.append)
    action = RedactFields(query={"term": {"ssn": "1"}}, fields=["ssn"], message="X")
    with patch("es_tools.redact.fields.Task") as task_cls:
        task_cls.return_value.wait.return_value = True
        result = action.execute(client, ["logs-1"], event_bus=bus, job_id="job-1")
    assert result.ok
    assert [e.hits for e in seen] == [5, 2]
    assert [e.iteration for e in seen] == [1, 2]
    assert seen[0].index == "logs-1"
    assert seen[0].job_id == "job-1"
