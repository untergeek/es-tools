"""Cluster routing transient settings action."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end

_ALLOCATION_VALUES = frozenset({"all", "primaries", "new_primaries", "none"})
_REBALANCE_VALUES = frozenset({"all", "primaries", "replicas", "none"})
_ROUTING_VALUES = {
    "allocation": _ALLOCATION_VALUES,
    "rebalance": _REBALANCE_VALUES,
}


class SetClusterRouting:
    """Set a transient cluster routing enable value.

    One ``cluster.put_settings(transient=...)`` call. Waits for relocating
    shards to settle (``wait_type="relocate"``, ``wait_mode="all"``).

    Args:
        routing_type: ``allocation`` or ``rebalance``.
        setting: Must be ``enable`` (Curator parity).
        value: One of the type-specific values.

    Example:
        >>> ActionRun(client, bus, "es-checkpoint").run(
        ...     SetClusterRouting("allocation", "enable", "primaries"),
        ...     ["cluster"],
        ... )
    """

    name = "cluster_routing"
    mode: Mode = "whole_list"
    wait_type: str | None = "relocate"
    wait_mode: str = "all"

    def __init__(
        self,
        routing_type: str,
        setting: str,
        value: str,
    ) -> None:
        if setting != "enable":
            raise ValueError(f'Invalid value for "setting": {setting}.')
        if routing_type not in _ROUTING_VALUES:
            raise ValueError(f'Invalid value for "routing_type": {routing_type}.')
        if value not in _ROUTING_VALUES[routing_type]:
            raise ValueError(
                f'Invalid "value": {value} with "routing_type": {routing_type}.'
            )
        bkey = f"cluster.routing.{routing_type}.{setting}"
        self.settings: dict[str, str] = {bkey: value}

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Call ``cluster.put_settings(transient=...)`` once.

        Args:
            client: Elasticsearch client (required positional).
            names: Single-element list; content is ignored (cluster scope).
            **opts: Unused.

        Returns:
            ExecuteResult with the raw ``put_settings`` response.
        """
        del opts
        raw = client.cluster.put_settings(transient=self.settings)
        return ExecuteResult(ok=True, names=names, raw=raw)
