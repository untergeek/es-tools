"""Delete indices in URI-sized chunks with retries."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end


class DeleteIndices:
    """Delete a list of indices, retrying each chunk up to three times.

    Example:
        >>> ActionRun(client, bus, "es-checkpoint").run(DeleteIndices(), ["old-1"])
    """

    name = "delete_indices"
    mode: Mode = "chunked"
    wait_type: str | None = None

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Delete ``names``, retrying leftovers up to three times.

        Args:
            client: Elasticsearch client.
            names: One URI chunk of index names.
            **opts: Unused.

        Returns:
            Failed ExecuteResult if any name remains after three tries.
        """
        remaining = list(names)
        for _ in range(3):
            if not remaining:
                break
            client.indices.delete(index=",".join(remaining), ignore_unavailable=True)
            remaining = [n for n in remaining if client.indices.exists(index=n)]
        if remaining:
            return ExecuteResult(
                ok=False,
                names=names,
                error=f"indices still present after 3 deletes: {remaining}",
            )
        return ExecuteResult(ok=True, names=names)
