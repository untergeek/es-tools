"""Set replica count in URI-sized chunks."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end


class SetReplicas:
    """Set ``number_of_replicas`` on a list of indices.

    Args:
        count: Replica count. Zero is allowed.

    Example:
        >>> SetReplicas(1)
    """

    name = "replicas"
    mode: Mode = "chunked"

    def __init__(self, count: int) -> None:
        if not isinstance(count, int) or count < 0:
            raise ValueError("count must be an integer >= 0")
        self.count = count
        self.wait_type: str | None = "relocate" if count > 0 else None

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Update replica count on ``names``.

        Args:
            client: Elasticsearch client.
            names: One URI chunk of index names.
            **opts: Unused.

        Returns:
            ExecuteResult for the chunk.
        """
        client.indices.put_settings(
            index=",".join(names),
            settings={"index": {"number_of_replicas": self.count}},
        )
        return ExecuteResult(ok=True, names=names)
