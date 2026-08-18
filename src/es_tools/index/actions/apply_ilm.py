"""Attach a cloned ILM policy to mounted indices."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end


class ApplyIlmPolicy:
    """PUT index.lifecycle settings (cloned policy name) on each index."""

    name = "apply_ilm_policy"
    mode: Mode = "per_item"
    wait_type: str | None = None

    def __init__(self, lifecycle: dict[str, Any]) -> None:
        if not lifecycle.get("name"):
            raise ValueError("lifecycle must include name")
        self.lifecycle = dict(lifecycle)

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Apply lifecycle settings to ``names[0]``."""
        del opts
        client.indices.put_settings(
            index=names[0], settings={"index": {"lifecycle": self.lifecycle}}
        )
        return ExecuteResult(ok=True, names=names)
