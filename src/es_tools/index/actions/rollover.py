"""Rollover aliases, one alias name per Step."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end


class RolloverIndices:
    """Rollover each alias if ``conditions`` are met.

    ``wait_for_active_shards`` is passed to ES; this action does not use
    an ActionRun waiter.

    Args:
        conditions: Rollover conditions (``max_age``, ``max_docs``, …).
            An empty dict means unconditional rollover.
        new_index: Optional name for the new index.
        extra_settings: Settings applied to the new index.
        wait_for_active_shards: ES ``wait_for_active_shards`` (default 1).

    Example:
        >>> ActionRun(client, bus, "es-checkpoint").run(
        ...     RolloverIndices({"max_age": "7d"}), ["logs-write"]
        ... )
    """

    name = "rollover"
    mode: Mode = "per_item"
    wait_type: str | None = None

    def __init__(
        self,
        conditions: dict[str, Any],
        *,
        new_index: str | None = None,
        extra_settings: dict[str, Any] | None = None,
        wait_for_active_shards: int = 1,
    ) -> None:
        if wait_for_active_shards < 1:
            raise ValueError("wait_for_active_shards must be >= 1")
        self.conditions = conditions
        self.new_index = new_index
        self.extra_settings = extra_settings
        self.wait_for_active_shards = wait_for_active_shards

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Rollover ``names[0]``.

        Args:
            client: Elasticsearch client.
            names: One-item unit (the alias name).
            **opts: Unused.

        Returns:
            ExecuteResult with the raw rollover response.
        """
        del opts
        kwargs: dict[str, Any] = {
            "alias": names[0],
            "wait_for_active_shards": self.wait_for_active_shards,
        }
        if self.conditions:
            kwargs["conditions"] = self.conditions
        if self.new_index is not None:
            kwargs["new_index"] = self.new_index
        if self.extra_settings is not None:
            kwargs["settings"] = self.extra_settings
        raw = client.indices.rollover(**kwargs)
        return ExecuteResult(ok=True, names=names, raw=raw)
