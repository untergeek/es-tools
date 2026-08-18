"""Base SnapshotTool class for es_tools.snapshot.

Provides a unified interface for Elasticsearch snapshot and repository operations.

Example:
    >>> from elasticsearch9 import Elasticsearch
    >>> from es_tools.snapshot import SnapshotTool
    >>> client = Elasticsearch()
    >>> tool = SnapshotTool(client)
    >>> tool.snapshot("my_snapshot", repository="my_repo")
"""

import logging
from typing import Any

from es_tools.debug import begin_end, debug

logger = logging.getLogger(__name__)


class SnapshotTool:
    """Snapshot and repository operations for Elasticsearch.

    Args:
        client: Elasticsearch client instance.

    Example:
        >>> from elasticsearch9 import Elasticsearch
        >>> from es_tools.snapshot import SnapshotTool
        >>> client = Elasticsearch()
        >>> tool = SnapshotTool(client)
        >>> tool.snapshot("my_snapshot", repository="my_repo")
    """

    def __init__(self, client: Any):
        self.client = client
        debug.lv2("Initializing SnapshotTool object")

    @begin_end()
    def snapshot(
        self,
        snapshot_name: str,
        repository: str,
        indices: list[str] | None = None,
        wait_for_completion: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a snapshot.

        Creates a snapshot of the specified indices in the given repository.
        Optionally waits for the snapshot to complete before returning.

        Args:
            snapshot_name: Name of the snapshot.
            repository: Snapshot repository name.
            indices: List of indices to snapshot (default: all).
            wait_for_completion: Wait for snapshot to complete (default: True).
            **kwargs: Additional parameters.

        Returns:
            Snapshot response dictionary.

        Example:
            >>> tool.snapshot("snap_1", "my_repo", indices=["index1", "index2"])
            {'acknowledged': True, 'snapshot': {...}}
        """
        debug.lv2(f"Creating snapshot: {snapshot_name}")
        body: dict[str, Any] = {}
        if indices:
            body["indices"] = ",".join(indices)
        body.update(kwargs)

        response = self.client.snapshot.create(
            repository=repository,
            snapshot=snapshot_name,
            body=body,
            wait_for_completion=wait_for_completion,
        )
        return response

    @begin_end()
    def restore(
        self,
        snapshot_name: str,
        repository: str,
        indices: list[str] | None = None,
        wait_for_completion: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Restore a snapshot.

        Restores the specified snapshot from the given repository.
        Optionally restores only specific indices.

        Args:
            snapshot_name: Name of the snapshot.
            repository: Snapshot repository name.
            indices: List of indices to restore (default: all).
            wait_for_completion: If True, block until primary recoveries
                finish. Default False — callers should wait via
                ``wait.Restore``.

        Returns:
            Restore response dictionary.

        Example:
            >>> tool.restore("snap_1", "my_repo", indices=["index1"])
            {'acknowledged': True}
        """
        debug.lv2(f"Restoring snapshot: {snapshot_name}")
        body: dict[str, Any] = {}
        if indices:
            body["indices"] = ",".join(indices)
        body.update(kwargs)

        response = self.client.snapshot.restore(
            repository=repository,
            snapshot=snapshot_name,
            body=body,
            wait_for_completion=wait_for_completion,
        )
        return response

    @begin_end()
    def delete_snapshot(
        self,
        snapshot_name: str,
        repository: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Delete a snapshot.

        Deletes the specified snapshot from the given repository.

        Args:
            snapshot_name: Name of the snapshot.
            repository: Snapshot repository name.
            **kwargs: Additional parameters.

        Returns:
            Delete response dictionary.

        Example:
            >>> tool.delete_snapshot("snap_1", "my_repo")
            {'acknowledged': True}
        """
        debug.lv2(f"Deleting snapshot: {snapshot_name}")
        response = self.client.snapshot.delete(
            repository=repository,
            snapshot=snapshot_name,
            **kwargs,
        )
        return response

    @begin_end()
    def get_snapshot_status(
        self,
        snapshot_name: str,
        repository: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Get snapshot status.

        Retrieves the current status of a snapshot.

        Args:
            snapshot_name: Name of the snapshot.
            repository: Snapshot repository name.
            **kwargs: Additional parameters.

        Returns:
            Snapshot status dictionary.

        Example:
            >>> status = tool.get_snapshot_status("snap_1", "my_repo")
            >>> status["snapshots"][0]["state"]
            'SUCCESS'
        """
        debug.lv2(f"Getting snapshot status: {snapshot_name}")
        response = self.client.snapshot.status(
            repository=repository,
            snapshot=snapshot_name,
            **kwargs,
        )
        return response

    @begin_end()
    def list_snapshots(
        self,
        repository: str,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """List snapshots in a repository.

        Retrieves a list of all snapshots in the specified repository.

        Args:
            repository: Snapshot repository name.
            **kwargs: Additional parameters.

        Returns:
            List of snapshot dictionaries.

        Example:
            >>> snapshots = tool.list_snapshots("my_repo")
            >>> len(snapshots)
            5
        """
        debug.lv2(f"Listing snapshots in repository: {repository}")
        response = self.client.snapshot.get(
            repository=repository,
            **kwargs,
        )
        return response.get("snapshots", [])

    @begin_end()
    def create_repository(
        self,
        repository_name: str,
        repository_type: str,
        settings: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a snapshot repository.

        Creates a new snapshot repository with the specified type and settings.

        Args:
            repository_name: Repository name.
            repository_type: Repository type (e.g., 'fs', 's3').
            settings: Repository settings.
            **kwargs: Additional parameters.

        Returns:
            Create response dictionary.

        Example:
            >>> tool.create_repository("my_repo", "fs", {"location": "/mnt/backups"})
            {'acknowledged': True}
        """
        debug.lv2(f"Creating repository: {repository_name}")
        body: dict[str, Any] = {
            "type": repository_type,
            "settings": settings,
        }
        body.update(kwargs)

        response = self.client.snapshot.create_repository(
            repository=repository_name,
            body=body,
        )
        return response

    @begin_end()
    def delete_repository(
        self,
        repository_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Delete a snapshot repository.

        Deletes the specified snapshot repository.

        Args:
            repository_name: Repository name.
            **kwargs: Additional parameters.

        Returns:
            Delete response dictionary.

        Example:
            >>> tool.delete_repository("my_repo")
            {'acknowledged': True}
        """
        debug.lv2(f"Deleting repository: {repository_name}")
        response = self.client.snapshot.delete_repository(
            repository=repository_name,
            **kwargs,
        )
        return response

    @begin_end()
    def verify_repository(
        self,
        repository_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Verify a snapshot repository.

        Verifies that the specified repository is accessible and functional.

        Args:
            repository_name: Repository name.
            **kwargs: Additional parameters.

        Returns:
            Verify response dictionary.

        Example:
            >>> result = tool.verify_repository("my_repo")
            >>> result["node"]["id"]
            'node_1'
        """
        debug.lv2(f"Verifying repository: {repository_name}")
        response = self.client.snapshot.verify_repository(
            repository=repository_name,
            **kwargs,
        )
        return response
