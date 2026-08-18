"""es_tools.snapshot module.

Snapshot and repository operations for Elasticsearch.

Provides utilities for managing snapshots and repositories, including
creating, restoring, deleting, and verifying snapshots and repositories.

Example:
    >>> from elasticsearch9 import Elasticsearch
    >>> from es_tools.snapshot import SnapshotTool
    >>> client = Elasticsearch()
    >>> tool = SnapshotTool(client)
    >>> tool.snapshot("my_snapshot", repository="my_repo")
"""

from .actions import CreateSnapshot, DeleteSnapshots, RestoreSnapshot
from .base import SnapshotTool

__all__ = [
    "CreateSnapshot",
    "DeleteSnapshots",
    "RestoreSnapshot",
    "SnapshotTool",
]
