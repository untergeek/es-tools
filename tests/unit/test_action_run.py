"""Unit tests for ActionRun (one Job, many Steps)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from es_tools.checkpoint.action_run import ActionRun, ExecuteResult, Mode
from es_tools.checkpoint.event_bus import EventBus


class DummyChunked:
    """Chunked dummy that records execute calls."""

    name = "dummy"
    mode: Mode = "chunked"
    wait_type = None

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        self.calls.append(list(names))
        return ExecuteResult(ok=True, names=names)


class DummyPerItem:
    """Per-item dummy."""

    name = "item"
    mode: Mode = "per_item"
    wait_type = None

    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        return ExecuteResult(ok=True, names=names)


class RecordsBus:
    """Records event_bus from execute opts."""

    name = "records"
    mode: Mode = "per_item"
    wait_type = None

    def __init__(self) -> None:
        self.bus: Any = None
        self.job_id: Any = None

    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        self.bus = opts.get("event_bus")
        self.job_id = opts.get("job_id")
        return ExecuteResult(ok=True, names=names)


class FailOnSecond:
    """Succeeds once, then fails."""

    name = "failer"
    mode: Mode = "chunked"
    wait_type = None

    def __init__(self) -> None:
        self.n = 0

    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        self.n += 1
        if self.n >= 2:
            return ExecuteResult(ok=False, names=names, error="boom")
        return ExecuteResult(ok=True, names=names)


class FailOnName:
    """Fails execute when the unit is exactly ``target``."""

    name = "failname"
    mode: Mode = "chunked"
    wait_type = None

    def __init__(self, target: str) -> None:
        self.target = target

    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        if names == [self.target]:
            return ExecuteResult(ok=False, names=names, error="boom")
        return ExecuteResult(ok=True, names=names)


class FailOnce:
    """Always fails execute with a fixed error string."""

    name = "failonce"
    mode: Mode = "chunked"
    wait_type = None

    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        return ExecuteResult(ok=False, names=names, error="nope")


def test_rejects_empty_names() -> None:
    """Empty name lists never start a Workbook."""
    run = ActionRun(object(), EventBus(), "es-checkpoint")
    with pytest.raises(ValueError, match="non-empty"):
        run.run(DummyChunked(), [])  # type: ignore


def test_chunked_is_one_job_many_steps() -> None:
    """Chunked mode uses one Job and one execute Step per chunk."""
    with patch(
        "es_tools.checkpoint.action_run.chunk_names",
        lambda names, max_bytes=3072: [["a"], ["b"]],
    ):
        wb = ActionRun(object(), EventBus(), "es-checkpoint").run(
            DummyChunked(), ["a", "b"]  # type: ignore
        )
    assert len(wb.jobs) == 1
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1", "execute-2"]
    assert wb.status == "COMPLETED"
    assert wb.jobs[0].status == "COMPLETED"


def test_per_item_is_one_job_step_per_name() -> None:
    """Per-item mode uses one Job and one Step per name."""
    wb = ActionRun(object(), EventBus(), "es-checkpoint").run(
        DummyPerItem(), ["a", "b"]  # type: ignore
    )
    assert len(wb.jobs) == 1
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1", "execute-2"]


def test_execute_opts_include_event_bus() -> None:
    """ActionRun passes its EventBus into execute opts."""
    bus = EventBus()
    action = RecordsBus()
    ActionRun(object(), bus, "es-checkpoint").run(action, ["a"])  # type: ignore[arg-type]
    assert action.bus is bus
    assert action.job_id


def test_on_error_stop_cancels_remaining_steps() -> None:
    """stop policy fails the Job and cancels the Workbook."""
    with patch(
        "es_tools.checkpoint.action_run.chunk_names",
        lambda names, max_bytes=3072: [["a"], ["b"]],
    ):
        wb = ActionRun(object(), EventBus(), "es-checkpoint", on_error="stop").run(
            FailOnSecond(), ["a", "b"]  # type: ignore
        )
    assert wb.jobs[0].status == "FAILED"
    assert wb.status in {"FAILED", "CANCELLED"}
    assert len(wb.jobs[0].steps) == 2


def test_on_error_continue_runs_remaining() -> None:
    """continue policy still executes later units after a failed execute."""
    with patch(
        "es_tools.checkpoint.action_run.chunk_names",
        lambda names, max_bytes=3072: [["a"], ["b"], ["c"]],
    ):
        wb = ActionRun(object(), EventBus(), "es-checkpoint", on_error="continue").run(
            FailOnName("b"), ["a", "b", "c"]  # type: ignore
        )
    steps = wb.jobs[0].steps
    assert [s.name for s in steps] == ["execute-1", "execute-2", "execute-3"]
    assert [s.status for s in steps] == ["COMPLETED", "FAILED", "COMPLETED"]
    assert steps[1]._error == "boom"
    assert wb.failures == [
        {"names": ["b"], "step": "execute-2", "error": "boom"},
    ]
    assert "b" in (wb.jobs[0]._error or "")
    assert "boom" in (wb.jobs[0]._error or "")
    assert wb.jobs[0].status == "FAILED"
    assert wb.status == "CANCELLED"


def test_execute_false_fails_step_with_error_string() -> None:
    """ExecuteResult(ok=False) fails the Step with the domain error, not RuntimeError."""
    wb = ActionRun(object(), EventBus(), "es-checkpoint").run(FailOnce(), ["a"])  # type: ignore
    step = wb.jobs[0].steps[0]
    assert step.status == "FAILED"
    assert step._error == "nope"
    assert wb.jobs[0].status == "FAILED"
    assert wb.status == "CANCELLED"


def test_dry_run_skips_execute() -> None:
    """dry_run completes events without calling execute."""
    dummy = DummyChunked()
    wb = ActionRun(object(), EventBus(), "es-checkpoint", dry_run=True).run(
        dummy, ["a"]  # type: ignore
    )
    assert dummy.calls == []
    assert wb.status == "COMPLETED"


def test_dry_run_does_not_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """dry_run must not honor per-item delay."""
    slept: list[float] = []
    monkeypatch.setattr(
        "es_tools.checkpoint.action_run.time.sleep",
        lambda s: slept.append(s),
    )
    ActionRun(object(), EventBus(), "es-checkpoint", dry_run=True).run(
        DummyPerItem(), ["a", "b"], delay=9  # type: ignore
    )
    assert slept == []


def test_per_item_delay_sleeps_between_units(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live per-item delay sleeps once between units, not after the last."""
    slept: list[float] = []
    monkeypatch.setattr(
        "es_tools.checkpoint.action_run.time.sleep",
        lambda s: slept.append(s),
    )
    ActionRun(object(), EventBus(), "es-checkpoint").run(
        DummyPerItem(), ["a", "b"], delay=3  # type: ignore
    )
    assert slept == [3.0]


class DummyPre:
    """Dummy with pre_execute and no delete_aliases dependency."""

    name = "pre"
    mode: Mode = "chunked"
    wait_type = None

    def __init__(self) -> None:
        self.pre: list[list[str]] = []

    def pre_execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        self.pre.append(list(names))
        return ExecuteResult(ok=True, names=names)

    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        return ExecuteResult(ok=True, names=names)


def test_pre_execute_runs_without_delete_aliases() -> None:
    """pre_execute runs for any action; default Step name is pre-N."""
    dummy = DummyPre()
    wb = ActionRun(object(), EventBus(), "es-checkpoint").run(dummy, ["a"])  # type: ignore
    assert dummy.pre == [["a"]]
    assert [s.name for s in wb.jobs[0].steps] == ["pre-1", "execute-1"]
    assert [r["step"] for r in wb.results] == ["pre-1", "execute-1"]


def test_pre_step_name_none_skips_pre_step() -> None:
    """pre_step_name returning None skips pre_execute."""
    dummy = DummyPre()
    dummy.pre_step_name = lambda index, **opts: None  # type: ignore
    wb = ActionRun(object(), EventBus(), "es-checkpoint").run(dummy, ["a"])  # type: ignore
    assert dummy.pre == []
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1"]


def test_action_named_close_without_execute_step_name_is_execute() -> None:
    """ActionRun must not special-case action.name == 'close'."""

    class NamedClose:
        name = "close"
        mode: Mode = "whole_list"
        wait_type = None

        def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
            return ExecuteResult(ok=True, names=names)

    wb = ActionRun(object(), EventBus(), "es-checkpoint").run(NamedClose(), ["a"])  # type: ignore
    assert [s.name for s in wb.jobs[0].steps] == ["execute-1"]


def test_pre_step_name_custom() -> None:
    """pre_step_name supplies the Step name."""
    dummy = DummyPre()
    dummy.pre_step_name = lambda index, **opts: f"prep-{index}"  # type: ignore
    wb = ActionRun(object(), EventBus(), "es-checkpoint").run(dummy, ["a"])  # type: ignore
    assert dummy.pre == [["a"]]
    assert [s.name for s in wb.jobs[0].steps] == ["prep-1", "execute-1"]


class FailPreOnFirst(DummyPre):
    """Fails pre_execute on the first unit only."""

    def pre_execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        self.pre.append(list(names))
        if len(self.pre) == 1:
            return ExecuteResult(ok=False, names=names, error="pre-boom")
        return ExecuteResult(ok=True, names=names)


def test_on_error_continue_pre_skips_unit_execute() -> None:
    """continue after a failed pre_execute skips that unit's execute, then proceeds."""
    dummy = FailPreOnFirst()
    with patch(
        "es_tools.checkpoint.action_run.chunk_names",
        lambda names, max_bytes=3072: [["a"], ["b"]],
    ):
        wb = ActionRun(object(), EventBus(), "es-checkpoint", on_error="continue").run(
            dummy, ["a", "b"]  # type: ignore
        )
    assert dummy.pre == [["a"], ["b"]]
    steps = wb.jobs[0].steps
    assert [s.name for s in steps] == ["pre-1", "pre-2", "execute-2"]
    assert steps[0].status == "FAILED"
    assert steps[0]._error == "pre-boom"
    assert steps[1].status == "COMPLETED"
    assert steps[2].status == "COMPLETED"
    assert wb.failures == [
        {"names": ["a"], "step": "pre-1", "error": "pre-boom"},
    ]
    assert wb.jobs[0].status == "FAILED"
    assert wb.status == "CANCELLED"


class FailPipe:
    """Pipeline that fails the second op of the first unit."""

    name = "failpipe"
    mode: Mode = "per_item"
    wait_type: str | None = None

    def pipeline(self, index: int, names: list[str], **opts: Any) -> list:
        from es_tools.checkpoint.action_run import StepSpec

        return [
            StepSpec(f"one-{index}", op="one"),
            StepSpec(f"two-{index}", op="two"),
        ]

    def run_step(
        self, spec, client: Any, names: list[str], **opts: Any
    ) -> ExecuteResult:
        if spec.op == "two" and names == ["a"]:
            return ExecuteResult(ok=False, names=names, error="pipe-boom")
        return ExecuteResult(ok=True, names=names)

    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        raise AssertionError("execute must not run when pipeline is set")


def test_on_error_continue_records_pipeline_failure() -> None:
    """Pipeline step failures append to Workbook.failures under continue."""
    wb = ActionRun(object(), EventBus(), "es-checkpoint", on_error="continue").run(
        FailPipe(), ["a", "b"]
    )
    assert wb.failures == [
        {"names": ["a"], "step": "two-1", "error": "pipe-boom"},
    ]
    assert "pipe-boom" in (wb.jobs[0]._error or "")


def test_persist_false_is_default() -> None:
    """Library ActionRun does not attach ElasticsearchBackend."""
    run = ActionRun(object(), EventBus(), "es-checkpoint")
    assert run.persist is False
    assert run.backend is None


def test_persist_true_constructs_backend() -> None:
    """persist=True subscribes ElasticsearchBackend before run()."""
    bus = EventBus()
    client = object()
    with patch("es_tools.checkpoint.action_run.ElasticsearchBackend") as backend_cls:
        sentinel = object()
        backend_cls.return_value = sentinel
        run = ActionRun(client, bus, "es-checkpoint", persist=True)
        backend_cls.assert_called_once_with(client, bus, "es-checkpoint")
        assert run.backend is sentinel


class DummyWithRaw:
    """whole_list dummy that returns a caller-supplied ExecuteResult."""

    name = "rawdummy"
    mode: Mode = "whole_list"
    wait_type = None

    def __init__(
        self,
        raw: Any = None,
        *,
        ok: bool = True,
        error: str | None = None,
    ) -> None:
        self._raw = raw
        self._ok = ok
        self._error = error

    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        return ExecuteResult(
            ok=self._ok, names=names, raw=self._raw, error=self._error
        )


def test_execute_result_dict_raw_on_workbook_results() -> None:
    """Dict raw is snapshotted; rolled_over false stays COMPLETED."""
    raw = {"rolled_over": False}
    wb = ActionRun(object(), EventBus(), "es-checkpoint").run(
        DummyWithRaw(raw), ["logs-write"]  # type: ignore[arg-type]
    )
    assert wb.status == "COMPLETED"
    assert len(wb.results) == 1
    assert wb.results[0] == {
        "ok": True,
        "names": ["logs-write"],
        "raw": {"rolled_over": False},
        "task_id": None,
        "error": None,
        "step": "execute-1",
    }
    json.dumps(wb.results)


def test_execute_result_body_attr_on_workbook_results() -> None:
    """ObjectApiResponse-like .body dict is stored, not the wrapper."""
    raw = SimpleNamespace(body={"rolled_over": False})
    wb = ActionRun(object(), EventBus(), "es-checkpoint").run(
        DummyWithRaw(raw), ["logs-write"]  # type: ignore[arg-type]
    )
    assert wb.status == "COMPLETED"
    assert wb.results[0]["raw"]["rolled_over"] is False
    json.dumps(wb.results)


def test_dry_run_does_not_record_results() -> None:
    """dry_run completes with empty workbook.results."""
    wb = ActionRun(object(), EventBus(), "es-checkpoint", dry_run=True).run(
        DummyWithRaw({"rolled_over": False}), ["a"]  # type: ignore[arg-type]
    )
    assert wb.status == "COMPLETED"
    assert wb.results == []


def test_execute_false_records_result_then_cancels() -> None:
    """ok=False is snapshotted; workbook is still cancelled."""
    wb = ActionRun(object(), EventBus(), "es-checkpoint").run(
        DummyWithRaw({"rolled_over": False}, ok=False, error="nope"),  # type: ignore[arg-type]
        ["a"],
    )
    assert wb.status == "CANCELLED"
    assert len(wb.results) == 1
    assert wb.results[0]["ok"] is False
    assert wb.results[0]["error"] == "nope"
    assert wb.results[0]["raw"]["rolled_over"] is False
    assert wb.results[0]["step"] == "execute-1"
    json.dumps(wb.results)
