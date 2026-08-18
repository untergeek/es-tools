"""Job class for event-driven checkpoint management.

Jobs represent individual units of work within a Workbook. Each Job can be
started, completed, or failed, and emit events on state changes. Jobs can
either be user-driven (manual lifecycle) or ES-driven (monitoring an external
Elasticsearch task_id).
"""

from __future__ import annotations

import sys

# Remove this block when the lowest version is 3.12+
if sys.version_info >= (3, 12):
    from typing import override  # pyright: ignore[reportUnreachable]
else:
    from typing_extensions import override

import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from .event_bus import EventBus
from .events import (
    JobCompleted,
    JobFailed,
    JobPaused,
    JobResumed,
    JobStarted,
    StatusChanged,
)
from .step import Step

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from elasticsearch9 import Elasticsearch


class Job:
    """Job represents an individual unit of work within a Workbook.

    A Job can be either:

    - **User-driven**: manual lifecycle (start → complete/fail)
    - **ES-driven**: monitors an external Elasticsearch task_id via
      ``tasks.get()`` polling until completion

    Args:
        event_bus: Event bus for publishing events.
        tracking_index: Name of the tracking index.
        doc_id: Unique ID for the job.
        workbook_name: Name of the parent workbook.
        index: Index name for the job.
        client: Elasticsearch client. Required; used by ES-driven monitoring
            and forwarded to every Step.
        task_id: If provided, monitor this ES task_id (ES-driven mode).
        pause: Seconds between polling iterations (ES-driven mode).
        timeout: Maximum seconds to wait for completion (ES-driven mode).

    Example (user-driven):
        >>> from es_tools.checkpoint.event_bus import EventBus
        >>> bus = EventBus()
        >>> job = Job(bus, "es-checkpoint", "wb1-index1", "wb1", "index1", client)
        >>> job.start()
        JobStarted(job_id="wb1-index1", ...)

    Example (ES-driven):
        >>> job = Job(bus, "es-checkpoint", "wb1-reindex", "wb1", "index1",
        ...           client, task_id="abc123")
        >>> job.start()  # begins monitoring task_id=abc123
    """

    def __init__(
        self,
        event_bus: EventBus,
        tracking_index: str,
        doc_id: str,
        workbook_name: str,
        index: str,
        client: Elasticsearch,
        task_id: str = "",
        pause: float = 9.0,
        timeout: float = 7200.0,
    ) -> None:
        self.event_bus: EventBus = event_bus
        self.tracking_index: str = tracking_index
        self.doc_id: str = doc_id
        self.workbook_name: str = workbook_name
        self.index: str = index
        self.client: Elasticsearch = client
        self.task_id: str = task_id
        self.poll_pause: float = pause
        self.timeout: float = timeout
        self.status: str = "PENDING"
        self.steps: list[Step] = []
        self.created_at: datetime = datetime.now(UTC)
        self.updated_at: datetime = datetime.now(UTC)
        self._error: str | None = None

    @property
    def job_id(self) -> str:
        """Get the job ID (same as doc_id)."""
        return self.doc_id

    def start(self) -> JobStarted:
        """Start the job.

        If ``task_id`` is provided, begins monitoring the external ES task
        (ES-driven mode) and **blocks** until the poll loop finishes
        (success, fail, or timeout; default timeout 7200s). ActionRun does
        not use this path; it waits via ``es_tools.wait``. Otherwise,
        emits a ``JobStarted`` event (user-driven mode) and returns
        immediately.

        Returns:
            JobStarted event.

        Raises:
            RuntimeError: If job is already running.
        """
        if self.status == "RUNNING":
            raise RuntimeError(f"Job {self.doc_id} is already running")

        old_status = self.status
        self.status = "RUNNING"
        self.updated_at = datetime.now(UTC)

        event = JobStarted(
            job_id=self.job_id,
            workbook_id=self.workbook_name,
            index=self.index,
        )
        self.event_bus.publish(event)
        self._emit_status_change(old_status, "RUNNING")
        logger.info("Job %s started", self.doc_id)

        if self.task_id:
            self._start_monitoring()

        return event

    def _start_monitoring(self) -> None:
        """Poll ES tasks.get() until the external task completes."""
        start_time = time.time()
        while self.status == "RUNNING":
            elapsed = time.time() - start_time
            if elapsed > self.timeout:
                _ = self.fail(f"Job {self.doc_id} timed out after {self.timeout}s")
                return
            try:
                response = self.client.tasks.get(task_id=self.task_id)
            except Exception as exc:
                logger.warning("Job %s: task polling error: %s", self.doc_id, exc)
                time.sleep(self.poll_pause)
                continue
            if response.completed:
                _ = self.complete()
                return
            time.sleep(self.poll_pause)

    def complete(self) -> JobCompleted:
        """Complete the job successfully and emit JobCompleted event.

        Returns:
            JobCompleted event.

        Raises:
            RuntimeError: If job is not running.
        """
        if self.status != "RUNNING":
            raise RuntimeError(
                f"Job {self.doc_id} is not running (status: {self.status})"
            )

        old_status = self.status
        self.status = "COMPLETED"
        self.updated_at = datetime.now(UTC)

        event = JobCompleted(
            job_id=self.job_id,
            workbook_id=self.workbook_name,
        )
        self.event_bus.publish(event)
        self._emit_status_change(old_status, "COMPLETED")
        logger.info("Job %s completed", self.doc_id)
        return event

    def fail(self, error: str) -> JobFailed:
        """Fail the job and emit JobFailed event.

        Args:
            error: Error message.

        Returns:
            JobFailed event.

        Raises:
            RuntimeError: If job is not running.
        """
        if self.status != "RUNNING":
            raise RuntimeError(
                f"Job {self.doc_id} is not running (status: {self.status})"
            )

        old_status = self.status
        self.status = "FAILED"
        self.updated_at = datetime.now(UTC)
        self._error = error

        event = JobFailed(
            job_id=self.job_id,
            workbook_id=self.workbook_name,
            error=error,
        )
        self.event_bus.publish(event)
        self._emit_status_change(old_status, "FAILED")
        logger.error("Job %s failed: %s", self.doc_id, error)
        return event

    def pause(self) -> JobPaused:
        """Pause the job and emit JobPaused event.

        Returns:
            JobPaused event.

        Raises:
            RuntimeError: If job is not running.
        """
        if self.status != "RUNNING":
            raise RuntimeError(
                f"Job {self.doc_id} is not running (status: {self.status})"
            )

        old_status = self.status
        self.status = "PAUSED"
        self.updated_at = datetime.now(UTC)

        event = JobPaused(job_id=self.job_id, workbook_id=self.workbook_name)
        self.event_bus.publish(event)
        self._emit_status_change(old_status, "PAUSED")
        logger.info("Job %s paused", self.doc_id)
        return event

    def resume(self) -> JobResumed:
        """Resume a paused job and emit JobResumed event.

        Returns:
            JobResumed event.

        Raises:
            RuntimeError: If job is not paused.
        """
        if self.status != "PAUSED":
            raise RuntimeError(
                f"Job {self.doc_id} is not paused (status: {self.status})"
            )

        old_status = self.status
        self.status = "RUNNING"
        self.updated_at = datetime.now(UTC)

        event = JobResumed(job_id=self.job_id, workbook_id=self.workbook_name)
        self.event_bus.publish(event)
        self._emit_status_change(old_status, "RUNNING")
        logger.info("Job %s resumed", self.doc_id)

        if self.task_id:
            self._start_monitoring()

        return event

    def create_step(
        self,
        number: int,
        name: str,
        *,
        check_type: str | None = None,
        check_value: str | None = None,
        check_index: str | None = None,
        pause: float = 1.0,
        timeout: float = 60.0,
    ) -> Step:
        """Create a new step for this job.

        The step receives this job's ``client``.

        Args:
            number: Step number. Must be >= 1.
            name: Step name.
            check_type: Optional ES state to monitor.
            check_value: Expected value for the state check.
            check_index: Index for ``ilm_phase`` / ``ilm_step``.
            pause: Seconds between polling iterations (state-driven mode).
            timeout: Maximum seconds to wait (state-driven mode).

        Returns:
            New Step instance.

        Raises:
            ValueError: If number < 1.
        """
        if number < 1:
            raise ValueError("number must be an integer >= 1")

        step_id = f"{self.doc_id}-step-{number}"
        step = Step(
            self.event_bus,
            self.tracking_index,
            step_id,
            self.doc_id,
            number,
            name,
            self.client,
            check_type=check_type,
            check_value=check_value,
            check_index=check_index,
            pause=pause,
            timeout=timeout,
        )
        self.steps.append(step)
        logger.debug("Created step %s for job %s", step_id, self.doc_id)
        return step

    def _emit_status_change(self, old_status: str, new_status: str) -> None:
        """Emit a StatusChanged event.

        Args:
            old_status: Previous status.
            new_status: New status.
        """
        event = StatusChanged(
            entity_type="Job",
            entity_id=self.doc_id,
            old_status=old_status,
            new_status=new_status,
        )
        self.event_bus.publish(event)

    @override
    def __repr__(self) -> str:
        return f"Job(workbook={self.workbook_name!r}, job={self.doc_id!r}, status={self.status!r})"
