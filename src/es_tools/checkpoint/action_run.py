"""Run list actions as one checkpoint Job with a Step per unit."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import uuid4

from es_tools.exceptions import ESToolActionError
from es_tools.utils.chunk import chunk_names
from es_tools.wait.dispatch import wait_on

from .event_bus import EventBus
from .storage import ElasticsearchBackend
from .workbook import Workbook

Mode = Literal["per_item", "chunked", "whole_list"]


@dataclass
class StepSpec:
    """One Step in an optional per-unit pipeline.

    Args:
        name: Checkpoint Step name.
        op: Action-defined operation key for ``run_step``.
        wait_type: If set, this spec is a wait-only Step.
    """

    name: str
    op: str = ""
    wait_type: str | None = None


@dataclass
class ExecuteResult:
    """Outcome of one action unit (chunk, item, or whole list).

    Args:
        ok: Whether the unit succeeded.
        names: Names acted on in this unit.
        raw: Optional raw ES response.
        task_id: Optional ES task id (restore wait).
        error: Failure message when ``ok`` is False.
    """

    ok: bool
    names: list[str]
    raw: Any = None
    task_id: str | None = None
    error: str | None = None


@dataclass
class _StepOutcome:
    """Result of one named checkpoint Step."""

    step_no: int
    ok: bool
    stop: bool
    result: Any = None
    step: Any = None


class ListAction(Protocol):
    """Contract for a list-in index or snapshot action."""

    name: str
    mode: Mode
    wait_type: str | None

    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Perform the action on ``names``."""
        ...


def _jsonish_raw(raw: Any) -> Any:
    """ES body as a mapping, or None."""
    if raw is None or isinstance(raw, dict):
        return raw
    body = getattr(raw, "body", None)
    if isinstance(body, dict):
        return body
    if isinstance(raw, Mapping):
        return dict(raw)
    return None


def _record_result(workbook: Workbook, result: Any, step: str) -> None:
    """Append one JSON-safe ExecuteResult snapshot."""
    if not isinstance(result, ExecuteResult):
        return
    workbook.results.append(
        {
            "ok": result.ok,
            "names": list(result.names),
            "raw": _jsonish_raw(result.raw),
            "task_id": result.task_id,
            "error": result.error,
            "step": step,
        }
    )


class ActionRun:
    """Execute a list action under one Workbook / one Job / many Steps.

    Args:
        client: Elasticsearch client.
        event_bus: Checkpoint event bus.
        tracking_index: Tracking index name.
        dry_run: If True, emit events but do not call ES.
        persist: If True, attach ``ElasticsearchBackend`` so events are
            written to ``tracking_index``. Library default is False;
            CLI/app callers must pass True.
        on_error: ``stop`` cancels remaining steps; ``continue`` proceeds.

    Example:
        >>> run = ActionRun(client, EventBus(), "es-checkpoint")
        >>> wb = run.run(OpenIndices(), ["logs-1", "logs-2"])
        >>> wb.jobs[0].index
        'open:2'
    """

    def __init__(
        self,
        client: Any,
        event_bus: EventBus,
        tracking_index: str,
        *,
        dry_run: bool = False,
        persist: bool = False,
        on_error: str = "stop",
    ) -> None:
        if on_error not in {"stop", "continue"}:
            raise ValueError("on_error must be 'stop' or 'continue'")
        self.client = client
        self.event_bus = event_bus
        self.tracking_index = tracking_index
        self.dry_run = dry_run
        self.persist = persist
        self.on_error = on_error
        self.backend: ElasticsearchBackend | None = None
        if persist:
            self.backend = ElasticsearchBackend(
                client, event_bus, tracking_index
            )

    def run(self, action: ListAction, names: list[str], **opts: Any) -> Workbook:
        """Run ``action`` against ``names``.

        Args:
            action: List action implementation.
            names: Index or snapshot names. Must be non-empty.
            **opts: Action options (skip_flush, delay, wait_for_completion, ...).

        ``action.mode`` controls how ``names`` is split into execution units:
        ``per_item`` runs one unit per name, ``chunked`` groups them, and
        ``whole_list`` runs the entire list as a single unit. Each unit is
        executed as its own step (see ``_run_unit``).

        Returns:
            Completed, failed, or cancelled Workbook.

        Raises:
            ValueError: If ``names`` is empty.
        """
        if not names:
            raise ValueError("names must be a non-empty list")

        units = self._units(action, names)
        wb = Workbook(
            self.event_bus,
            self.tracking_index,
            f"{action.name}-{uuid4().hex[:8]}",
            {
                "action": action.name,
                "count": len(names),
                **{k: v for k, v in opts.items() if k != "settings"},
            },
            dry_run=self.dry_run,
        )
        wb.start()
        job = wb.create_job(f"{action.name}:{len(names)}", self.client)
        job.start()
        step_no = 0
        any_failed = False
        try:
            for i, unit in enumerate(units, start=1):
                step_no, unit_failed, stop = self._run_unit(
                    action, job, wb, unit, i, step_no, opts
                )
                if unit_failed:
                    any_failed = True
                    if stop:
                        return wb
                self._maybe_delay(action, i, len(units), opts)

            return self._finish(wb, job, any_failed)
        except Exception as exc:
            if job.status == "RUNNING":
                job.fail(str(exc))
            if wb.status == "RUNNING":
                wb.cancel(str(exc))
            raise

    def _record_failure(
        self, workbook: Workbook, unit: list[str], step: str, error: str
    ) -> None:
        """Append one unit failure onto ``workbook.failures``."""
        workbook.failures.append(
            {"names": list(unit), "step": step, "error": error}
        )

    def _stop_unit(
        self,
        job: Any,
        workbook: Workbook,
        unit: list[str],
        step: Any | None,
        msg: str,
        *,
        fail_step: bool,
    ) -> bool:
        """Record a unit failure. Return True if the caller must return the workbook."""
        if fail_step and step is not None:
            step.fail(msg)
        self._record_failure(
            workbook, unit, step.name if step is not None else "?", msg
        )
        if self.on_error == "stop":
            job.fail(msg)
            workbook.cancel(msg)
            return True
        return False

    def _maybe_delay(
        self,
        action: ListAction,
        index: int,
        unit_count: int,
        opts: dict[str, Any],
    ) -> None:
        delay = float(opts.get("delay") or 0)
        if (
            delay > 0
            and action.mode == "per_item"
            and index < unit_count
            and not self.dry_run
        ):
            time.sleep(delay)

    def _pre_name(
        self, action: ListAction, index: int, opts: dict[str, Any]
    ) -> str | None:
        name_fn = getattr(action, "pre_step_name", None)
        if callable(name_fn):
            pre_name = name_fn(index, **opts)
            if pre_name is None:
                return None
            return str(pre_name)
        if callable(getattr(action, "pre_execute", None)):
            return f"pre-{index}"
        return None

    def _execute_name(
        self, action: ListAction, index: int, opts: dict[str, Any]
    ) -> str:
        name_fn = getattr(action, "execute_step_name", None)
        if callable(name_fn):
            return str(name_fn(index, **opts))
        return f"execute-{index}"

    def _run_unit(
        self,
        action: ListAction,
        job: Any,
        workbook: Workbook,
        unit: list[str],
        index: int,
        step_no: int,
        opts: dict[str, Any],
    ) -> tuple[int, bool, bool]:
        """Run one unit. Returns ``(step_no, failed, stop)``."""
        pipe_fn = getattr(action, "pipeline", None)
        if callable(pipe_fn):
            step_no, unit_failed = self._run_pipeline(
                action, job, workbook, unit, index, step_no, opts
            )
            return step_no, unit_failed, unit_failed and self.on_error == "stop"

        pre_fn = getattr(action, "pre_execute", None)
        pre_name = self._pre_name(action, index, opts)
        if pre_name:
            pre_out = self._run_named_step(
                job,
                workbook,
                unit,
                step_no,
                str(pre_name),
                lambda fn=pre_fn, names=unit, kw=opts: (
                    fn(self.client, names, **kw) if callable(fn) else None
                ),
                failed_msg="pre_execute failed",
            )
            step_no = pre_out.step_no
            if not pre_out.ok:
                return step_no, True, pre_out.stop

        exec_kw = {
            **opts,
            "event_bus": opts.get("event_bus", self.event_bus),
            "job_id": opts.get("job_id", job.job_id),
        }
        exec_out = self._run_named_step(
            job,
            workbook,
            unit,
            step_no,
            self._execute_name(action, index, opts),
            lambda act=action, names=unit, kw=exec_kw: act.execute(
                self.client, names, **kw
            ),
            failed_msg="action failed",
        )
        step_no = exec_out.step_no
        if not exec_out.ok:
            return step_no, True, exec_out.stop

        if (
            not self.dry_run
            and action.wait_type
            and opts.get("wait_for_completion", True)
        ):
            wait_out = self._run_wait_step(
                job,
                workbook,
                action,
                exec_out.result,
                unit,
                index,
                step_no,
                opts,
                exec_out.step,
            )
            step_no = wait_out.step_no
            if not wait_out.ok:
                return step_no, True, wait_out.stop
        return step_no, False, False

    def _finish(
        self, workbook: Workbook, job: Any, any_failed: bool
    ) -> Workbook:
        if any_failed:
            summary = self._failure_summary(workbook)
            job.fail(summary)
            workbook.cancel(summary)
            return workbook
        job.complete()
        workbook.complete(list(workbook.results))
        return workbook

    def _run_named_step(
        self,
        job: Any,
        workbook: Workbook,
        unit: list[str],
        step_no: int,
        name: str,
        call: Callable[[], Any],
        *,
        failed_msg: str,
    ) -> _StepOutcome:
        step_no += 1
        step = job.create_step(step_no, name)
        step.start()
        if self.dry_run:
            step.complete()
            return _StepOutcome(step_no=step_no, ok=True, stop=False, step=step)
        try:
            result = call()
            _record_result(workbook, result, name)
            if result is not None and not getattr(result, "ok", True):
                msg = getattr(result, "error", None) or failed_msg
                stop = self._stop_unit(
                    job, workbook, unit, step, msg, fail_step=True
                )
                return _StepOutcome(
                    step_no=step_no, ok=False, stop=stop, result=result, step=step
                )
            step.complete()
            return _StepOutcome(
                step_no=step_no, ok=True, stop=False, result=result, step=step
            )
        except Exception as exc:
            stop = self._stop_unit(
                job,
                workbook,
                unit,
                step,
                str(exc),
                fail_step=(step.status == "RUNNING"),
            )
            return _StepOutcome(step_no=step_no, ok=False, stop=stop, step=step)

    def _run_wait_step(
        self,
        job: Any,
        workbook: Workbook,
        action: ListAction,
        result: Any,
        unit: list[str],
        index: int,
        step_no: int,
        opts: dict[str, Any],
        exec_step: Any,
    ) -> _StepOutcome:
        step_no += 1
        wstep = job.create_step(step_no, f"wait-{index}")
        wstep.start()
        try:
            self._wait(action, result, unit, opts)
            wstep.complete()
            return _StepOutcome(step_no=step_no, ok=True, stop=False, step=wstep)
        except Exception as exc:
            current = None
            if wstep.status == "RUNNING":
                current = wstep
            elif exec_step is not None and exec_step.status == "RUNNING":
                current = exec_step
            if current is not None:
                stop = self._stop_unit(
                    job, workbook, unit, current, str(exc), fail_step=True
                )
            else:
                stop = self._stop_unit(
                    job, workbook, unit, exec_step, str(exc), fail_step=False
                )
            return _StepOutcome(step_no=step_no, ok=False, stop=stop, step=wstep)

    def _failure_summary(self, workbook: Workbook) -> str:
        """Join recorded failures into a Job/Workbook reason string."""
        if not workbook.failures:
            return "one or more steps failed"
        return "; ".join(
            f"{','.join(f['names'])} ({f['step']}): {f['error']}"
            for f in workbook.failures
        )

    def _units(self, action: ListAction, names: list[str]) -> list[list[str]]:
        """Split ``names`` according to ``action.mode``."""
        if action.mode == "per_item":
            return [[name] for name in names]
        if action.mode == "whole_list":
            return [list(names)]
        return chunk_names(names)

    def _run_pipeline(
        self,
        action: ListAction,
        job: Any,
        workbook: Workbook,
        unit: list[str],
        index: int,
        step_no: int,
        opts: dict[str, Any],
    ) -> tuple[int, bool]:
        """Run ``action.pipeline`` specs as Steps.

        Returns:
            Tuple of the next step number and whether this unit failed.
        """
        pipe_fn = getattr(action, "pipeline", None)
        if not callable(pipe_fn):
            raise ESToolActionError("pipeline action is missing pipeline")
        specs_obj = pipe_fn(index, unit, **opts)
        if not isinstance(specs_obj, (list, tuple)):
            raise ESToolActionError("pipeline must return a list of StepSpec")
        specs = list(specs_obj)
        run_step = getattr(action, "run_step", None)
        for spec in specs:
            step_no += 1
            step = job.create_step(step_no, spec.name)
            step.start()
            if self.dry_run:
                step.complete()
                continue
            try:
                if spec.wait_type:
                    self._wait_type(
                        spec.wait_type,
                        ExecuteResult(ok=True, names=unit),
                        unit,
                        opts,
                        action,
                    )
                    step.complete()
                    continue
                if not callable(run_step):
                    raise ESToolActionError("pipeline action is missing run_step")
                result = run_step(spec, self.client, unit, **opts)
                if result is not None and not getattr(result, "ok", True):
                    msg = getattr(result, "error", None) or "pipeline step failed"
                    self._stop_unit(
                        job, workbook, unit, step, msg, fail_step=True
                    )
                    return step_no, True
                step.complete()
            except Exception as exc:
                self._stop_unit(
                    job,
                    workbook,
                    unit,
                    step,
                    str(exc),
                    fail_step=(step.status == "RUNNING"),
                )
                return step_no, True
        return step_no, False

    def _wait(
        self,
        action: ListAction,
        result: ExecuteResult,
        names: list[str],
        opts: dict[str, Any],
    ) -> None:
        """Block on the waiter declared by ``action.wait_type``."""
        if not action.wait_type:
            raise ESToolActionError("wait_type is not set")
        self._wait_type(action.wait_type, result, names, opts, action)

    def _wait_type(
        self,
        wait_type: str,
        result: ExecuteResult,
        names: list[str],
        opts: dict[str, Any],
        action: ListAction | None = None,
    ) -> None:
        """Block on a named waiter."""
        wait_on(wait_type, self.client, result, names, opts, action)
