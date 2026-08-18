"""Relocate Waiter for es_tools.wait."""

from __future__ import annotations

import logging
import typing as t

from es_tools.debug import begin_end, debug

from ._base import Waiter
from .defaults import RELOCATE
from .utils import prettystr

if t.TYPE_CHECKING:
    from elasticsearch9 import Elasticsearch

logger = logging.getLogger(__name__)

_MODES = frozenset({"selected", "all"})


class Relocate(Waiter):
    """Wait for shard relocation to complete.

    Two modes:

    * ``selected`` (default): every shard copy of the selected indices is
      ``STARTED``. ``UNASSIGNED`` / ``RELOCATING`` / ``INITIALIZING`` and a
      missing routing-table entry are not done. Optional ``node`` requires
      every copy STARTED on that node.
    * ``all``: cluster-wide ``relocating_shards == 0`` via ``cluster.health``.

    Args:
        client: Elasticsearch client.
        indices: Index names to wait on (used in ``selected`` mode).
        mode: ``selected`` or ``all``.
        node: If set, every shard copy must be STARTED on this node.
        pause: Seconds between checks (default: 3.0).
        timeout: Max wait time in seconds (default: 120.0).
        max_exceptions: Max allowed exceptions (default: 10).

    Example:
        >>> waiter = Relocate(client, indices=["my_index"])
        >>> waiter.wait()
    """

    def __init__(
        self,
        client: Elasticsearch,
        indices: list[str],
        mode: str = "selected",
        node: str | None = None,
        pause: float = RELOCATE["pause"],
        timeout: float = RELOCATE["timeout"],
        max_exceptions: int = RELOCATE["max_exceptions"],
    ) -> None:
        if mode not in _MODES:
            raise ValueError(f"mode must be 'selected' or 'all', got {mode!r}")
        super().__init__(
            client=client, pause=pause, timeout=timeout, max_exceptions=max_exceptions
        )
        debug.lv2("Initializing Relocate object...")
        self.indices = indices
        self.mode = mode
        self.node = node
        scope = "all shards" if mode == "all" else f"indices {self.indices}"
        self.waitstr = f"for {scope} to be relocated"
        self.announce()
        debug.lv3("Relocate object initialized")

    def __repr__(self) -> str:
        """Return a string representation of the Relocate instance."""
        return (
            f"Relocate(indices={self.indices!r}, mode={self.mode!r}, "
            f"node={self.node!r}, waitstr={self.waitstr!r}, pause={self.pause})"
        )

    @begin_end()
    def check(self) -> bool:
        """Check whether the waited-on shards have settled.

        Returns:
            True when the wait condition is met.
        """
        self.too_many_exceptions()
        try:
            if self.mode == "all":
                return self._check_all()
            return self._check_selected()
        except Exception as err:
            self.add_exception(err)
            logger.error("Error getting cluster state: %s", prettystr(err))
            return False

    def _check_all(self) -> bool:
        """Return True when cluster-wide relocating_shards is 0."""
        debug.lv4("TRY: Getting cluster health")
        health = self.client.cluster.health()
        relocating = int(health.get("relocating_shards", 0))
        if relocating == 0:
            return True
        logger.info("Shards still relocating: %d", relocating)
        return False

    def _check_selected(self) -> bool:
        """Return True when every selected shard copy is STARTED."""
        debug.lv4("TRY: Getting cluster state")
        kwargs: dict[str, t.Any] = {"metric": ["routing_table"]}
        if self.indices:
            kwargs["index"] = self.indices
        state = self.client.cluster.state(**kwargs)
        routing = state.get("routing_table", {}).get("indices", {})
        still: list[str] = []
        for name in self.indices:
            entry = routing.get(name)
            if entry is None or _index_unsettled(entry, self.node):
                still.append(name)
        if not still:
            return True
        logger.info("Indices still relocating: %s", still)
        return False


def _index_unsettled(entry: dict[str, t.Any], node: str | None) -> bool:
    """Return True if any shard copy is not STARTED (on ``node`` if set)."""
    shards = entry.get("shards") or {}
    if not shards:
        return True
    for copies in shards.values():
        if not copies:
            return True
        for shard in copies:
            if shard.get("state") != "STARTED":
                return True
            if node is not None and shard.get("node") != node:
                return True
    return False
