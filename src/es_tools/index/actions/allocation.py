"""Set shard allocation filters in URI-sized chunks."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end

_VALID_TYPES = frozenset({"require", "include", "exclude"})


class SetAllocation:
    """Set ``index.routing.allocation.{type}.{key}`` on a list of indices.

    Args:
        key: Allocation attribute key.
        value: Allocation attribute value.
        allocation_type: ``require``, ``include``, or ``exclude``.

    Example:
        >>> SetAllocation(key="tag", value="hot", allocation_type="require")
    """

    name = "allocation"
    mode: Mode = "chunked"
    wait_type: str | None = "relocate"

    def __init__(
        self,
        key: str,
        value: str | None = None,
        allocation_type: str = "require",
    ) -> None:
        if not key:
            raise ValueError("key is required")
        if allocation_type not in _VALID_TYPES:
            raise ValueError(f"allocation_type must be one of {sorted(_VALID_TYPES)}")
        self.key = key
        self.value = value
        self.allocation_type = allocation_type

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Apply the allocation setting to ``names``.

        Args:
            client: Elasticsearch client.
            names: One URI chunk of index names.
            **opts: Unused.

        Returns:
            ExecuteResult for the chunk.
        """
        setting_key = f"index.routing.allocation.{self.allocation_type}.{self.key}"
        client.indices.put_settings(
            index=",".join(names),
            settings={setting_key: self.value},
        )
        return ExecuteResult(ok=True, names=names)
