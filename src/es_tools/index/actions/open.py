"""Open indices in URI-sized chunks."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end


class OpenIndices:
    """Open a list of indices.

    No constructor arguments. Options are passed through ``ActionRun.run``.

    Example:
        >>> ActionRun(client, bus, "es-checkpoint").run(OpenIndices(), ["a", "b"])
    """

    name = "open"
    mode: Mode = "chunked"
    wait_type: str | None = None

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Open ``names`` as a CSV URI.

        Args:
            client: Elasticsearch client.
            names: One URI chunk of index names.
            **opts: Unused.

        Returns:
            ExecuteResult for the chunk.
        """
        client.indices.open(index=",".join(names), ignore_unavailable=True)
        return ExecuteResult(ok=True, names=names)
