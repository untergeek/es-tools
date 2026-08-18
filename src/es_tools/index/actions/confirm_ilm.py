"""Advance a mounted index to a target ILM phase (pii-tool confirm_ilm_phase)."""

from __future__ import annotations

from time import sleep
from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode, StepSpec
from es_tools.debug import begin_end
from es_tools.exceptions import ESToolActionError
from es_tools.wait.defaults import ILM
from es_tools.wait.ilm import PHASE_ORDER, IlmPhase, IlmStep, explain_index

_TARGET_PHASES = tuple(p for p in PHASE_ORDER if p != "new")
_MOVE_ATTEMPTS = 3


class ConfirmIlmPhase:
    """Wait until the index is at ``phase`` / complete, moving ILM if needed.

    Per index: wait phase ``new``-or-later + step ``complete``, then
    ``ilm.move_to_step`` unless already at the target complete step, then
    wait for the target phase + ``complete``.

    Args:
        phase: Target ILM phase (hot/warm/cold/frozen/delete). Not ``new``.

    Raises:
        ValueError: If ``phase`` is empty, ``new``, or unknown.
    """

    name = "confirm_ilm_phase"
    mode: Mode = "per_item"
    wait_type: str | None = None

    def __init__(self, phase: str) -> None:
        if phase not in _TARGET_PHASES:
            raise ValueError(f"phase must be one of {_TARGET_PHASES}, got {phase!r}")
        self.phase = phase

    def pipeline(self, index: int, names: list[str], **opts: Any) -> list[StepSpec]:
        """Return wait-new → move → wait-target."""
        del names, opts
        return [
            StepSpec(f"wait-new-{index}", op="wait_new"),
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
        if spec.op == "wait_new":
            IlmPhase(client, index=index, phase="new").wait()
            IlmStep(client, index=index, step="complete").wait()
            return ExecuteResult(ok=True, names=names)
        if spec.op == "move":
            return self._move(client, index)
        if spec.op == "wait_target":
            IlmPhase(client, index=index, phase=self.phase).wait()
            IlmStep(client, index=index, step="complete").wait()
            return ExecuteResult(ok=True, names=names)
        raise ESToolActionError(f"unknown confirm_ilm_phase op: {spec.op}")

    def _current(self, info: dict[str, Any]) -> dict[str, str]:
        return {
            "phase": str(info.get("phase") or ""),
            "action": str(info.get("action") or ""),
            "name": str(info.get("step") or ""),
        }

    def _move(self, client: Any, index: str) -> ExecuteResult:
        target = {
            "phase": self.phase,
            "action": "complete",
            "name": "complete",
        }
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
