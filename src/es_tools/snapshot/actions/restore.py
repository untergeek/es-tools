"""Restore one snapshot (JSON body, never chunked)."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end


class RestoreSnapshot:
    """Restore a snapshot, optionally limited to ``names``.

    Args:
        repository: Snapshot repository.
        snapshot: Snapshot name.

    Example:
        >>> RestoreSnapshot(repository="repo", snapshot="snap-1")
    """

    name = "restore"
    mode: Mode = "whole_list"
    wait_type: str | None = "restore"

    def __init__(self, repository: str, snapshot: str) -> None:
        if not repository or not snapshot:
            raise ValueError("repository and snapshot are required")
        self.repository = repository
        self.snapshot = snapshot

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Restore the snapshot.

        Args:
            client: Elasticsearch client.
            names: Indices to restore (full list in the body).
            **opts: Unused.

        Returns:
            ExecuteResult with the raw restore response.
        """
        raw = client.snapshot.restore(
            repository=self.repository,
            snapshot=self.snapshot,
            indices=names,
            wait_for_completion=False,
        )
        return ExecuteResult(ok=True, names=names, raw=raw)
