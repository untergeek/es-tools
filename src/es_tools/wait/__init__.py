"""Utilities for waiting on Elasticsearch operations.

The es_tools.wait package provides classes to wait for completion of
Elasticsearch tasks, such as index relocation, snapshot creation, and
ILM phase transitions. Each waiter polls the cluster state, handles
timeouts, and logs progress.

Example:
    >>> from es_tools.wait import Health
    >>> from elasticsearch9 import Elasticsearch
    >>> client = Elasticsearch()
    >>> waiter = Health(client, check_type="status")
    >>> waiter.wait()
"""

from .exists import Exists
from .health import Health
from .ilm import IlmPhase, IlmStep
from .relocate import Relocate
from .restore import Restore
from .snapshot import Snapshot
from .task import Task

__all__ = [
    "Exists",
    "Health",
    "IlmPhase",
    "IlmStep",
    "Relocate",
    "Restore",
    "Snapshot",
    "Task",
]
