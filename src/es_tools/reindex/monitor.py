"""ReindexMonitor class for es_tools.reindex.

Monitors multiple Elasticsearch reindex tasks simultaneously.

Example:
    >>> from elasticsearch9 import Elasticsearch
    >>> from es_tools.reindex import ReindexMonitor
    >>> client = Elasticsearch()
    >>> monitor = ReindexMonitor(client, ["task_1", "task_2"])
    >>> monitor.wait_all()
"""

import logging
from typing import Any

from es_tools.debug import begin_end, debug

from .task import ReindexTask

logger = logging.getLogger(__name__)


class ReindexMonitor:
    """Monitor multiple reindex tasks.

    Provides batch monitoring capabilities for multiple reindex operations.

    Args:
        client: Elasticsearch client.
        task_ids: List of task IDs to monitor.
        polling_interval: Seconds between status checks (default: 10).
        timeout: Maximum wait time in seconds (default: 7200).

    Example:
        >>> from elasticsearch9 import Elasticsearch
        >>> from es_tools.reindex import ReindexMonitor
        >>> client = Elasticsearch()
        >>> monitor = ReindexMonitor(client, ["task_1", "task_2"])
        >>> monitor.wait_all()
    """

    def __init__(
        self,
        client: Any,
        task_ids: list[str],
        polling_interval: float = 10.0,
        timeout: float = 7200.0,
    ):
        self.client = client
        self.task_ids = task_ids
        self.polling_interval = polling_interval
        self.timeout = timeout
        self.tasks: dict[str, ReindexTask] = {}
        debug.lv2(f"Initializing ReindexMonitor with {len(task_ids)} tasks")

    @begin_end()
    def _initialize_tasks(self) -> None:
        """Initialize ReindexTask instances for all task IDs.

        Creates ReindexTask objects for each task ID in the list.

        Example:
            >>> monitor._initialize_tasks()
        """
        for task_id in self.task_ids:
            task = ReindexTask(
                client=self.client,
                task_id=task_id,
                polling_interval=self.polling_interval,
                timeout=self.timeout,
            )
            self.tasks[task_id] = task
            debug.lv3(f"Initialized task: {task_id}")

    @property
    def all_completed(self) -> bool:
        """Check if all tasks are completed.

        Returns:
            True if all tasks are completed.

        Example:
            >>> monitor.all_completed
            False
        """
        if not self.tasks:
            self._initialize_tasks()
        return all(task.completed for task in self.tasks.values())

    @property
    def all_failed(self) -> bool:
        """Check if all tasks have failed.

        Returns:
            True if all tasks have failed.

        Example:
            >>> monitor.all_failed
            False
        """
        if not self.tasks:
            self._initialize_tasks()
        return all(task.failures > 0 for task in self.tasks.values())

    @begin_end()
    def wait_all(self) -> dict[str, dict[str, Any]]:
        """Wait for all tasks to complete.

        Waits for all monitored tasks to complete and returns their final data.

        Returns:
            Dictionary mapping task IDs to their final data.

        Raises:
            Exception: If any task fails.

        Example:
            >>> results = monitor.wait_all()
            >>> len(results)
            2
        """
        if not self.tasks:
            self._initialize_tasks()

        results = {}
        for task_id, task in self.tasks.items():
            debug.lv3(f"Waiting for task: {task_id}")
            try:
                results[task_id] = task.wait_for_completion()
            except Exception as exc:
                logger.error(f"Task {task_id} failed: {exc}")
                raise

        debug.lv2("All tasks completed")
        return results

    @begin_end()
    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all tasks.

        Returns aggregated statistics for all monitored tasks.

        Returns:
            Summary dictionary with task statistics.

        Example:
            >>> summary = monitor.get_summary()
            >>> summary["total_tasks"]
            2
            >>> summary["completed"]
            2
        """
        if not self.tasks:
            self._initialize_tasks()

        summary = {
            "total_tasks": len(self.tasks),
            "completed": 0,
            "running": 0,
            "failed": 0,
            "total_documents": 0,
            "total_created": 0,
            "total_updated": 0,
            "total_deleted": 0,
            "total_failures": 0,
        }

        for task in self.tasks.values():
            if task.completed:
                summary["completed"] += 1
            elif task.failures > 0:
                summary["failed"] += 1
            else:
                summary["running"] += 1

            summary["total_documents"] += task.total
            summary["total_created"] += task.created
            summary["total_updated"] += task.updated
            summary["total_deleted"] += task.deleted
            summary["total_failures"] += task.failures

        return summary

    def __repr__(self) -> str:
        """Return string representation."""
        return f"ReindexMonitor(tasks={len(self.tasks)}, all_completed={self.all_completed})"
