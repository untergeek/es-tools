"""ReindexTask class for es_tools.reindex.

Monitors Elasticsearch reindex tasks and provides progress tracking.

Example:
    >>> from elasticsearch9 import Elasticsearch
    >>> from es_tools.reindex import ReindexTask
    >>> client = Elasticsearch()
    >>> task = ReindexTask(client, "task_123")
    >>> task.wait_for_completion()
"""

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from elasticsearch9 import NotFoundError

from es_tools.debug import begin_end, debug
from es_tools.exceptions import (
    ESToolReindexError,
    ESToolTaskNotFoundError,
    ESToolTaskTimeoutError,
)

logger = logging.getLogger(__name__)


class ReindexTask:
    """Monitor an Elasticsearch reindex task.

    Provides methods to check task status, get progress, and wait for completion.

    Args:
        client: Elasticsearch client.
        task_id: Task ID to monitor.
        polling_interval: Seconds between status checks (default: 10).
        timeout: Maximum wait time in seconds (default: 7200).

    Example:
        >>> from elasticsearch9 import Elasticsearch
        >>> from es_tools.reindex import ReindexTask
        >>> client = Elasticsearch()
        >>> task = ReindexTask(client, "task_123")
        >>> task.status
        'RUNNING'
    """

    def __init__(
        self,
        client: Any,
        task_id: str,
        polling_interval: float = 10.0,
        timeout: float = 7200.0,
    ):
        self.client = client
        self.task_id = task_id
        self.polling_interval = polling_interval
        self.timeout = timeout
        self._data: dict[str, Any] | None = None
        self._start_time: datetime | None = None
        debug.lv2(f"Initializing ReindexTask: {task_id}")

    @begin_end()
    def _get_task_data(self) -> dict[str, Any]:
        """Get task data from Elasticsearch.

        Retrieves the current status and progress of the reindex task.

        Returns:
            Task data dictionary.

        Raises:
            ESToolTaskNotFoundError: If task not found.
            ESToolReindexError: If task polling fails for another reason.

        Example:
            >>> data = task._get_task_data()
            >>> data["completed"]
            True
        """
        try:
            response = dict(self.client.tasks.get(task_id=self.task_id))
            self._data = response
            if self._start_time is None:
                self._start_time = datetime.now(UTC)
            return self._data
        except NotFoundError as exc:
            logger.error(f"Task {self.task_id} not found: {exc}")
            raise ESToolTaskNotFoundError(
                f"Task {self.task_id} not found: {exc}"
            ) from exc
        except Exception as exc:
            logger.error(f"Failed to get task data for {self.task_id}: {exc}")
            raise ESToolReindexError(
                f"Failed to get task data for {self.task_id}: {exc}"
            ) from exc

    def _payload(self) -> dict[str, Any]:
        """Return the full GET /_tasks/{id} body, fetching if needed."""
        if self._data is None:
            self._get_task_data()
        return self._data or {}

    def _task_status(self) -> dict[str, Any]:
        """Return task.status counters from the payload."""
        return (self._payload().get("task") or {}).get("status") or {}

    @property
    def status(self) -> str:
        """Get the current task status.

        Returns:
            Task status string (e.g., 'RUNNING', 'COMPLETED', 'FAILED').

        Example:
            >>> task.status
            'RUNNING'
        """
        if self.completed:
            return "FAILED" if self.failures else "COMPLETED"
        return "RUNNING"

    @property
    def completed(self) -> bool:
        """Check if the task is completed.

        Returns:
            True if task is completed, False otherwise.

        Example:
            >>> task.completed
            False
        """
        return bool(self._payload().get("completed"))

    @property
    def total(self) -> int:
        """Get the total number of documents.

        Returns:
            Total documents count.

        Example:
            >>> task.total
            10000
        """
        return int(self._task_status().get("total") or 0)

    @property
    def created(self) -> int:
        """Get the number of documents created.

        Returns:
            Created documents count.

        Example:
            >>> task.created
            5000
        """
        return int(self._task_status().get("created") or 0)

    @property
    def updated(self) -> int:
        """Get the number of documents updated.

        Returns:
            Updated documents count.

        Example:
            >>> task.updated
            3000
        """
        return int(self._task_status().get("updated") or 0)

    @property
    def deleted(self) -> int:
        """Get the number of documents deleted.

        Returns:
            Deleted documents count.

        Example:
            >>> task.deleted
            1000
        """
        return int(self._task_status().get("deleted") or 0)

    @property
    def failures(self) -> int:
        """Get the number of failures.

        Returns:
            Failures count.

        Example:
            >>> task.failures
            0
        """
        fails = (self._payload().get("response") or {}).get("failures") or []
        return len(fails) if not isinstance(fails, int) else fails

    @property
    def elapsed_time(self) -> timedelta:
        """Get the elapsed time since task started.

        Returns:
            Elapsed time as timedelta.

        Example:
            >>> task.elapsed_time
            datetime.timedelta(seconds=30)
        """
        if self._start_time is None:
            self._get_task_data()
        start = self._start_time
        if start is None:
            return timedelta(0)
        return datetime.now(UTC) - start

    @property
    def progress(self) -> float:
        """Get the task progress as a percentage.

        Returns:
            Progress percentage (0-100).

        Example:
            >>> task.progress
            90.0
        """
        total = self.total
        if total == 0:
            return 0.0
        created = self.created
        updated = self.updated
        deleted = self.deleted
        return ((created + updated + deleted) / total) * 100

    @begin_end()
    def wait_for_completion(self, poll_interval: float | None = None) -> dict[str, Any]:
        """Wait for the task to complete.

        Polls the task status until it completes or times out.

        Args:
            poll_interval: Seconds between checks (default: polling_interval).

        Returns:
            Final task data dictionary.

        Raises:
            ESToolTaskTimeoutError: If timeout is reached.

        Example:
            >>> data = task.wait_for_completion()
            >>> data["completed"]
            True
        """
        if poll_interval is None:
            poll_interval = self.polling_interval

        debug.lv2(f"Waiting for task {self.task_id} to complete")
        start_time = time.time()

        while not self.completed:
            if time.time() - start_time > self.timeout:
                msg = f"Task {self.task_id} timed out after {self.timeout} seconds"
                logger.error(msg)
                raise ESToolTaskTimeoutError(msg)

            self._get_task_data()
            debug.lv3(
                f"Task {self.task_id}: {self.progress:.1f}% complete "
                f"({self.created + self.updated + self.deleted}/{self.total})"
            )
            time.sleep(poll_interval)

        debug.lv2(f"Task {self.task_id} completed")
        return self._data or {}

    def __repr__(self) -> str:
        """Return string representation."""
        return f"ReindexTask(task_id={self.task_id!r}, status={self.status!r})"
