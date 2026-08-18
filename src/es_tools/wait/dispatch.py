"""Named wait-type dispatch for ActionRun."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import es_tools.wait.ilm as wait_ilm
import es_tools.wait.relocate as wait_relocate
import es_tools.wait.restore as wait_restore
import es_tools.wait.snapshot as wait_snapshot
import es_tools.wait.task as wait_task
from es_tools.exceptions import ESToolActionError

DEFAULT_SNAPSHOT_WAIT = 7200.0


def _wait_relocate(
    client: Any,
    result: Any,
    names: list[str],
    opts: dict[str, Any],
    action: Any,
) -> None:
    wait_mode = opts.get("wait_mode")
    if wait_mode is None and action is not None:
        wait_mode = getattr(action, "wait_mode", None)
    if wait_mode is None:
        wait_mode = "selected"
    kwargs: dict[str, Any] = {"indices": names, "mode": wait_mode}
    node = opts.get("wait_node")
    if node is None and action is not None:
        node = getattr(action, "wait_node", None)
    if node:
        kwargs["node"] = node
    timeout = opts.get("timeout")
    if timeout is not None:
        kwargs["timeout"] = timeout
    wait_relocate.Relocate(client, **kwargs).wait()


def _wait_ilm_phase(
    client: Any,
    result: Any,
    names: list[str],
    opts: dict[str, Any],
    action: Any,
) -> None:
    if len(names) != 1:
        raise ESToolActionError("ilm_phase wait requires a single index")
    phase = opts.get("phase")
    if phase is None and action is not None:
        phase = getattr(action, "ilm_phase", None)
    if not phase:
        raise ESToolActionError("ilm_phase wait requires phase")
    ilm_kw: dict[str, Any] = {"index": names[0], "phase": phase}
    timeout = opts.get("timeout")
    if timeout is not None:
        ilm_kw["timeout"] = timeout
    wait_ilm.IlmPhase(client, **ilm_kw).wait()


def _wait_ilm_step(
    client: Any,
    result: Any,
    names: list[str],
    opts: dict[str, Any],
    action: Any,
) -> None:
    if len(names) != 1:
        raise ESToolActionError("ilm_step wait requires a single index")
    step = opts.get("step")
    if step is None and action is not None:
        step = getattr(action, "ilm_step", None)
    if not step:
        step = "complete"
    step_kw: dict[str, Any] = {"index": names[0], "step": step}
    timeout = opts.get("timeout")
    if timeout is not None:
        step_kw["timeout"] = timeout
    wait_ilm.IlmStep(client, **step_kw).wait()


def _wait_snapshot(
    client: Any,
    result: Any,
    names: list[str],
    opts: dict[str, Any],
    action: Any,
) -> None:
    repository = opts.get("repository") or getattr(action, "repository", None)
    snapshot = opts.get("snapshot") or getattr(action, "snapshot", None)
    if not repository or not snapshot:
        raise ESToolActionError(
            "snapshot wait requires repository and snapshot"
        )
    timeout = opts.get("timeout")
    snap_timeout = DEFAULT_SNAPSHOT_WAIT if timeout is None else timeout
    wait_snapshot.Snapshot(
        client,
        repository=repository,
        snapshot=snapshot,
        timeout=snap_timeout,
    ).wait()


def _wait_restore(
    client: Any,
    result: Any,
    names: list[str],
    opts: dict[str, Any],
    action: Any,
) -> None:
    timeout = opts.get("timeout")
    restore_timeout = DEFAULT_SNAPSHOT_WAIT if timeout is None else timeout
    wait_restore.Restore(
        client,
        indices=names,
        repository=opts.get("repository")
        or getattr(action, "repository", None),
        snapshot=opts.get("snapshot")
        or getattr(action, "snapshot", None),
        timeout=restore_timeout,
    ).wait()


def _wait_task(
    client: Any,
    result: Any,
    names: list[str],
    opts: dict[str, Any],
    action: Any,
) -> None:
    task_id = result.task_id
    if not task_id:
        raise ESToolActionError("task wait requires task_id")
    action_name = "reindex"
    if action is not None:
        action_name = getattr(action, "task_action", None) or "reindex"
    task_kwargs: dict[str, Any] = {"action": action_name, "task_id": task_id}
    timeout = opts.get("timeout")
    if timeout is not None:
        task_kwargs["timeout"] = timeout
    wait_task.Task(client, **task_kwargs).wait()


WAIT_TYPES: dict[str, Callable[..., None]] = {
    "relocate": _wait_relocate,
    "ilm_phase": _wait_ilm_phase,
    "ilm_step": _wait_ilm_step,
    "snapshot": _wait_snapshot,
    "restore": _wait_restore,
    "task": _wait_task,
}


def wait_on(
    wait_type: str,
    client: Any,
    result: Any,
    names: list[str],
    opts: dict[str, Any],
    action: Any = None,
) -> None:
    """Block on a named waiter."""
    builder = WAIT_TYPES.get(wait_type)
    if builder is None:
        raise ESToolActionError(f"unknown wait_type: {wait_type}")
    builder(client, result, names, opts, action)
