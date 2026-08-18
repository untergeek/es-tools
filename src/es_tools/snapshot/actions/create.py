"""Create one snapshot of the full index list (JSON body, never chunked)."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end


class CreateSnapshot:
    """Create a single snapshot covering every name in the list.

    Indices go in the request body. Concurrent snapshots are allowed; wait
    on repository+name after create.

    Args:
        repository: Snapshot repository.
        snapshot: Snapshot name.

    Example:
        >>> CreateSnapshot(repository="repo", snapshot="snap-1")
    """

    name = "snapshot"
    mode: Mode = "whole_list"
    wait_type: str | None = "snapshot"

    def __init__(self, repository: str, snapshot: str) -> None:
        if not repository or not snapshot:
            raise ValueError("repository and snapshot are required")
        self.repository = repository
        self.snapshot = snapshot

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Create the snapshot with ``names`` in the JSON body.

        Args:
            client: Elasticsearch client.
            names: Full index list (not a URI chunk).
            **opts: Unused.

        Returns:
            ExecuteResult with the raw create response.
        """
        raw = client.snapshot.create(
            repository=self.repository,
            snapshot=self.snapshot,
            indices=names,
            wait_for_completion=False,
        )
        return ExecuteResult(ok=True, names=names, raw=raw)
