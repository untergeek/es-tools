"""Add and/or remove indices on one alias in a single update_aliases call."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end


class UpdateAliases:
    """Update one alias for add and remove index lists.

    ``extra_settings`` is merged into each **add** action only (filters,
    routing, ``is_write_index``, …). Remove skips indices that do not
    currently hold the alias.

    Args:
        alias: Literal alias name. Date patterns are the caller's job.
        extra_settings: Extra keys for each add action.
        add: Indices to add to the alias.
        remove: Indices to remove from the alias.

    Raises:
        ValueError: If ``alias`` is empty, or both ``add`` and ``remove``
            are empty.

    Example:
        >>> action = UpdateAliases("logs-write", add=["logs-2"], remove=["logs-1"])
        >>> ActionRun(client, bus, "es-checkpoint").run(action, action.names)
    """

    name = "alias"
    mode: Mode = "whole_list"
    wait_type: str | None = None

    def __init__(
        self,
        alias: str,
        *,
        extra_settings: dict[str, Any] | None = None,
        add: Sequence[str] = (),
        remove: Sequence[str] = (),
    ) -> None:
        if not alias:
            raise ValueError("alias must be a non-empty string")
        add_names = list(add)
        remove_names = list(remove)
        if not add_names and not remove_names:
            raise ValueError("add and remove cannot both be empty")
        self.alias = alias
        self.extra_settings = dict(extra_settings or {})
        self.add = add_names
        self.remove = remove_names

    @property
    def names(self) -> list[str]:
        """Add names then remove names, for ``ActionRun.run`` / the Job label."""
        return [*self.add, *self.remove]

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Build add/remove actions and call ``update_aliases`` once.

        Args:
            client: Elasticsearch client.
            names: Unused; the ctor lists are the source of truth.
            **opts: Unused.

        Returns:
            ExecuteResult for the whole alias update.
        """
        del names, opts
        actions: list[dict[str, Any]] = []
        for index in self.add:
            add_body: dict[str, Any] = {"index": index, "alias": self.alias}
            add_body.update(self.extra_settings)
            actions.append({"add": add_body})
        if self.remove:
            held = client.indices.get_alias(
                index=",".join(self.remove),
                expand_wildcards=["open", "closed"],
            )
            for index in self.remove:
                aliases = held.get(index, {}).get("aliases", {})
                if self.alias in aliases:
                    actions.append({"remove": {"index": index, "alias": self.alias}})
        if actions:
            client.indices.update_aliases(actions=actions)
        return ExecuteResult(ok=True, names=self.names)
