"""Shrink each index onto one node, one pipeline of Steps per index."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode, StepSpec
from es_tools.debug import begin_end
from es_tools.exceptions import ESToolActionError


class ShrinkIndices:
    """Shrink each source index to fewer shards.

    ``shrink_node`` is a required node **name** (no DETERMINISTIC picker).
    Per index, ActionRun emits: route → wait-relocate → block-writes →
    shrink → optional aliases → delete or unroute.

    Args:
        shrink_node: Node name that will hold every shard before shrink.
        number_of_shards: Target primary shard count (default 1).
        number_of_replicas: Target replica count (default 1).
        shrink_prefix: Prepended to the target index name.
        shrink_suffix: Appended to the target index name (default ``-shrink``).
        copy_aliases: Move aliases from source to target after shrink.
        delete_after: Delete the source index after shrink (default True).
        wait_for_active_shards: Passed to ``indices.shrink``.

    Raises:
        ValueError: If ``shrink_node`` is empty, shard counts are < 1, or
            both prefix and suffix are empty.

    Example:
        >>> ActionRun(client, bus, "es-checkpoint").run(
        ...     ShrinkIndices("es-data-1"), ["logs-000001"]
        ... )
    """

    name = "shrink"
    mode: Mode = "per_item"
    wait_type: str | None = None

    def __init__(
        self,
        shrink_node: str,
        *,
        number_of_shards: int = 1,
        number_of_replicas: int = 1,
        shrink_prefix: str = "",
        shrink_suffix: str = "-shrink",
        copy_aliases: bool = False,
        delete_after: bool = True,
        wait_for_active_shards: int = 1,
    ) -> None:
        if not shrink_node:
            raise ValueError("shrink_node must be a non-empty string")
        if number_of_shards < 1:
            raise ValueError("number_of_shards must be >= 1")
        if number_of_replicas < 0:
            raise ValueError("number_of_replicas must be >= 0")
        if not shrink_prefix and not shrink_suffix:
            raise ValueError("shrink_prefix and shrink_suffix cannot both be empty")
        self.shrink_node = shrink_node
        self.wait_node = shrink_node
        self.number_of_shards = number_of_shards
        self.number_of_replicas = number_of_replicas
        self.shrink_prefix = shrink_prefix
        self.shrink_suffix = shrink_suffix
        self.copy_aliases = copy_aliases
        self.delete_after = delete_after
        self.wait_for_active_shards = wait_for_active_shards

    def target_name(self, source: str) -> str:
        """Return the shrunk index name for ``source``."""
        return f"{self.shrink_prefix}{source}{self.shrink_suffix}"

    def pipeline(self, index: int, names: list[str], **opts: Any) -> list[StepSpec]:
        """Return the per-index Step list.

        Args:
            index: 1-based unit number.
            names: One-item unit (source index).
            **opts: Unused.

        Returns:
            Ordered StepSpec list for this index.
        """
        del names, opts
        specs = [
            StepSpec(f"route-{index}", op="route"),
            StepSpec(f"wait-relocate-{index}", wait_type="relocate"),
            StepSpec(f"block-writes-{index}", op="block_writes"),
            StepSpec(f"shrink-{index}", op="shrink"),
        ]
        if self.copy_aliases:
            specs.append(StepSpec(f"aliases-{index}", op="aliases"))
        if self.delete_after:
            specs.append(StepSpec(f"delete-{index}", op="delete"))
        else:
            specs.append(StepSpec(f"unroute-{index}", op="unroute"))
        return specs

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Run the shrink HTTP call only (pipeline uses ``run_step``)."""
        return self._shrink(client, names[0])

    @begin_end()
    def run_step(
        self, spec: StepSpec, client: Any, names: list[str], **opts: Any
    ) -> ExecuteResult:
        """Dispatch one pipeline op.

        Args:
            spec: Step from ``pipeline``.
            client: Elasticsearch client.
            names: One-item unit (source index).
            **opts: Unused.

        Returns:
            ExecuteResult for this op.

        Raises:
            ESToolActionError: If ``spec.op`` is unknown.
        """
        del opts
        source = names[0]
        if spec.op == "route":
            self._route(client, source, self.shrink_node)
            return ExecuteResult(ok=True, names=names)
        if spec.op == "block_writes":
            client.indices.put_settings(
                index=source, settings={"index.blocks.write": True}
            )
            return ExecuteResult(ok=True, names=names)
        if spec.op == "shrink":
            return self._shrink(client, source)
        if spec.op == "aliases":
            self._copy_aliases(client, source, self.target_name(source))
            return ExecuteResult(ok=True, names=names)
        if spec.op == "delete":
            client.indices.delete(index=source)
            return ExecuteResult(ok=True, names=names)
        if spec.op == "unroute":
            self._route(client, source, None)
            return ExecuteResult(ok=True, names=names)
        raise ESToolActionError(f"unknown shrink op: {spec.op}")

    def _route(self, client: Any, index: str, node: str | None) -> None:
        client.indices.put_settings(
            index=index,
            settings={"index.routing.allocation.require._name": node},
        )

    def _shrink(self, client: Any, source: str) -> ExecuteResult:
        target = self.target_name(source)
        if client.indices.exists(index=target):
            return ExecuteResult(
                ok=False,
                names=[source],
                error=f"shrink target {target} already exists",
            )
        settings = {
            "index.number_of_shards": self.number_of_shards,
            "index.number_of_replicas": self.number_of_replicas,
            "index.routing.allocation.require._name": None,
            "index.blocks.write": None,
        }
        try:
            raw = client.indices.shrink(
                index=source,
                target=target,
                settings=settings,
                wait_for_active_shards=self.wait_for_active_shards,
            )
        except Exception:
            if client.indices.exists(index=target):
                client.indices.delete(index=target)
            raise
        return ExecuteResult(ok=True, names=[source], raw=raw)

    def _copy_aliases(self, client: Any, source: str, target: str) -> None:
        held = client.indices.get_alias(index=source)
        actions: list[dict[str, Any]] = []
        for alias in held.get(source, {}).get("aliases", {}):
            actions.append({"remove": {"index": source, "alias": alias}})
            actions.append({"add": {"index": target, "alias": alias}})
        if actions:
            client.indices.update_aliases(actions=actions)
