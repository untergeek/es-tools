"""Advance an ILM-managed index one phase."""

from __future__ import annotations

from time import sleep
from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode, StepSpec
from es_tools.debug import begin_end
from es_tools.exceptions import ESToolActionError
from es_tools.wait.defaults import ILM
from es_tools.wait.ilm import PHASE_ORDER, IlmPhase, IlmStep, explain_index
from es_tools.wait.utils import response_dict

_MOVE_ATTEMPTS = 3


def _backing_name(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("index_name") or item.get("index") or "")


def _is_write_backing(client: Any, index: str) -> bool:
    """True if ``index`` is a data stream's current write backing index."""
    entry = response_dict(client.indices.get(index=index)).get(index)
    if not isinstance(entry, dict):
        return False
    stream = entry.get("data_stream")
    if not isinstance(stream, str) or not stream:
        return False
    body = response_dict(client.indices.get_data_stream(name=stream))
    streams = body.get("data_streams") or []
    if not streams or not isinstance(streams[0], dict):
        return False
    indices = streams[0].get("indices") or []
    return bool(indices) and _backing_name(indices[-1]) == index


class PromoteIlm:
    """Move each index to the next ILM phase (not a named jump).

    Per index: explain, wait current step ``complete``, ``ilm.move_to_step``
    to the next phase's complete step, wait that phase + ``complete``.
    Already on ``delete`` is a no-op. Unmanaged indices fail the inspect
    Step (``explain_index``). A data stream's current write backing index
    is skipped (no wait, no ``move_to_step``).

    Size-based promote is for exceptions; ILM may move the index back if
    the policy disagrees — the wait Step re-reads ``explain_lifecycle``.

    Example:
        >>> ActionRun(client, bus, \"es-checkpoint\").run(PromoteIlm(), names)
    """

    name = "promote_ilm"
    mode: Mode = "per_item"
    wait_type: str | None = None

    def __init__(self) -> None:
        self._next: dict[str, str] = {}

    def pipeline(self, index: int, names: list[str], **opts: Any) -> list[StepSpec]:
        """Return inspect → move → wait-target."""
        del names, opts
        return [
            StepSpec(f"inspect-{index}", op="inspect"),
            StepSpec(f"move-{index}", op="move"),
            StepSpec(f"wait-target-{index}", op="wait_target"),
        ]

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Unused when pipeline is present; keep for ListAction."""
        del opts
        return self._move(client, names[0])

    @begin_end()
    def run_step(
        self, spec: StepSpec, client: Any, names: list[str], **opts: Any
    ) -> ExecuteResult:
        """Dispatch one pipeline op."""
        del opts
        index = names[0]
        if spec.op == "inspect":
            return self._inspect(client, index)
        if spec.op == "move":
            return self._move(client, index)
        if spec.op == "wait_target":
            nxt = self._next.get(index, "")
            if not nxt:
                return ExecuteResult(ok=True, names=names)
            IlmPhase(client, index=index, phase=nxt).wait()
            IlmStep(client, index=index, step="complete").wait()
            return ExecuteResult(ok=True, names=names)
        raise ESToolActionError(f"unknown promote_ilm op: {spec.op}")

    def _inspect(self, client: Any, index: str) -> ExecuteResult:
        info = explain_index(client, index)
        if _is_write_backing(client, index):
            self._next[index] = ""
            return ExecuteResult(ok=True, names=[index])
        current = str(info.get("phase") or "")
        if current not in PHASE_ORDER:
            raise ESToolActionError(f"unknown ILM phase {current!r} for {index!r}")
        pos = PHASE_ORDER.index(current)
        nxt = "" if pos >= len(PHASE_ORDER) - 1 else PHASE_ORDER[pos + 1]
        self._next[index] = nxt
        IlmStep(client, index=index, step="complete").wait()
        return ExecuteResult(ok=True, names=[index])

    def _current(self, info: dict[str, Any]) -> dict[str, str]:
        return {
            "phase": str(info.get("phase") or ""),
            "action": str(info.get("action") or ""),
            "name": str(info.get("step") or ""),
        }

    def _move(self, client: Any, index: str) -> ExecuteResult:
        nxt = self._next.get(index, "")
        if not nxt:
            return ExecuteResult(ok=True, names=[index])
        target = {"phase": nxt, "action": "complete", "name": "complete"}
        last_err: Exception | None = None
        for attempt in range(_MOVE_ATTEMPTS):
            info = explain_index(client, index)
            current = self._current(info)
            if current == target:
                return ExecuteResult(ok=True, names=[index])
            try:
                client.ilm.move_to_step(
                    index=index, current_step=current, next_step=target
                )
                return ExecuteResult(ok=True, names=[index])
            except Exception as exc:
                last_err = exc
                if attempt + 1 < _MOVE_ATTEMPTS:
                    sleep(float(ILM["pause"]))
        raise ESToolActionError(
            f"ilm.move_to_step failed for {index!r} after {_MOVE_ATTEMPTS} attempts: "
            f"{last_err}"
        ) from last_err
