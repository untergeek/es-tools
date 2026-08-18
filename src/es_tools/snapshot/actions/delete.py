"""Delete snapshots one name at a time."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end


class DeleteSnapshots:
    """Delete each snapshot as its own Step.

    Args:
        repository: Snapshot repository.

    Example:
        >>> DeleteSnapshots(repository="repo")
    """

    name = "delete_snapshots"
    mode: Mode = "per_item"
    wait_type: str | None = None

    def __init__(self, repository: str) -> None:
        if not repository:
            raise ValueError("repository is required")
        self.repository = repository

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Delete ``names[0]``.

        Args:
            client: Elasticsearch client.
            names: One-element list with the snapshot name.
            **opts: Unused.

        Returns:
            ExecuteResult for that snapshot.
        """
        raw = client.snapshot.delete(
            repository=self.repository, snapshot=names[0]
        )
        return ExecuteResult(ok=True, names=names, raw=raw)
