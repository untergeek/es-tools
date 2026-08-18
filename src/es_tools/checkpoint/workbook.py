"""Workbook class for event-driven checkpoint management.

Workbooks are top-level containers that hold multiple Jobs. Each Job represents
a unit of work with its own steps. Workbooks can be started, paused, resumed,
or cancelled.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .event_bus import EventBus
from .events import (
    StatusChanged,
    WorkbookCancelled,
    WorkbookCompleted,
    WorkbookPaused,
    WorkbookResumed,
    WorkbookStarted,
)
from .job import Job

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from elasticsearch9 import Elasticsearch


class Workbook:
    """Workbook represents a top-level container with lifecycle management.

    A Workbook contains multiple Jobs, each representing a unit of work.
    The Workbook tracks the overall progress and can be started, paused,
    resumed, or cancelled.

    Args:
        event_bus: Event bus for publishing events.
        tracking_index: Name of the tracking index.
        name: Unique name for the workbook.
        config: Configuration dictionary.
        dry_run: If True, skip data-cluster mutations. Events still fire
            and an attached backend still persists the audit trail.

    Example:
        >>> from es_tools.checkpoint.event_bus import EventBus
        >>> bus = EventBus()
        >>> wb = Workbook(bus, "es-checkpoint", "test_workbook", {"pattern": "*"})
        >>> wb.start()
        WorkbookStarted(workbook_id="test_workbook", ...)
    """

    def __init__(
        self,
        event_bus: EventBus,
        tracking_index: str,
        name: str,
        config: dict[str, Any],
        dry_run: bool = False,
    ) -> None:
        self.event_bus = event_bus
        self.tracking_index = tracking_index
        self.name = name
        self.config = config
        self.dry_run = dry_run
        self.status: str = "PENDING"
        self.jobs: list[Job] = []
        self.results: list[Any] = []
        self.failures: list[dict[str, Any]] = []
        self.created_at: datetime = datetime.now(UTC)
        self.updated_at: datetime = datetime.now(UTC)
        self._history: list[dict[str, Any]] = []

    @property
    def workbook_id(self) -> str:
        """Get the workbook ID (same as name)."""
        return self.name

    def start(self) -> WorkbookStarted:
        """Start the workbook and emit WorkbookStarted event.

        Returns:
            WorkbookStarted event.

        Raises:
            RuntimeError: If workbook is already running.
        """
        if self.status == "RUNNING":
            raise RuntimeError(f"Workbook {self.name} is already running")

        old_status = self.status
        self.status = "RUNNING"
        self.updated_at = datetime.now(UTC)

        published = {**self.config, "dry_run": self.dry_run}
        event = WorkbookStarted(
            workbook_id=self.workbook_id,
            workbook_name=self.name,
            config=published,
            dry_run=self.dry_run,
        )
        self.event_bus.publish(event)
        self._emit_status_change(old_status, "RUNNING")
        logger.info("Workbook %s started", self.name)
        return event

    def pause(self) -> WorkbookPaused:
        """Pause the workbook and emit WorkbookPaused event.

        Returns:
            WorkbookPaused event.

        Raises:
            RuntimeError: If workbook is not running.
        """
        if self.status != "RUNNING":
            raise RuntimeError(
                f"Workbook {self.name} is not running (status: {self.status})"
            )

        old_status = self.status
        self.status = "PAUSED"
        self.updated_at = datetime.now(UTC)

        event = WorkbookPaused(workbook_id=self.workbook_id, workbook_name=self.name)
        self.event_bus.publish(event)
        self._emit_status_change(old_status, "PAUSED")
        logger.info("Workbook %s paused", self.name)
        return event

    def resume(self) -> WorkbookResumed:
        """Resume a paused workbook and emit WorkbookResumed event.

        Returns:
            WorkbookResumed event.

        Raises:
            RuntimeError: If workbook is not paused.
        """
        if self.status != "PAUSED":
            raise RuntimeError(
                f"Workbook {self.name} is not paused (status: {self.status})"
            )

        old_status = self.status
        self.status = "RUNNING"
        self.updated_at = datetime.now(UTC)

        event = WorkbookResumed(workbook_id=self.workbook_id, workbook_name=self.name)
        self.event_bus.publish(event)
        self._emit_status_change(old_status, "RUNNING")
        logger.info("Workbook %s resumed", self.name)
        return event

    def complete(self, results: list[Any] | None = None) -> WorkbookCompleted:
        """Complete the workbook successfully and emit WorkbookCompleted event.

        Args:
            results: Optional list of results.

        Returns:
            WorkbookCompleted event.

        Raises:
            RuntimeError: If workbook is not running.
        """
        if self.status != "RUNNING":
            raise RuntimeError(
                f"Workbook {self.name} is not running (status: {self.status})"
            )

        old_status = self.status
        self.status = "COMPLETED"
        self.updated_at = datetime.now(UTC)
        self.results = results or []

        event = WorkbookCompleted(
            workbook_id=self.workbook_id,
            workbook_name=self.name,
            results=self.results,
        )
        self.event_bus.publish(event)
        self._emit_status_change(old_status, "COMPLETED")
        logger.info(
            "Workbook %s completed with %d results", self.name, len(self.results)
        )
        return event

    def cancel(self, reason: str = "") -> WorkbookCancelled:
        """Cancel the workbook and emit WorkbookCancelled event.

        Args:
            reason: Optional cancellation reason.

        Returns:
            WorkbookCancelled event.

        Raises:
            RuntimeError: If workbook is not running or paused.
        """
        if self.status not in ("RUNNING", "PAUSED"):
            raise RuntimeError(
                f"Workbook {self.name} cannot be cancelled (status: {self.status})"
            )

        old_status = self.status
        self.status = "CANCELLED"
        self.updated_at = datetime.now(UTC)

        event = WorkbookCancelled(
            workbook_id=self.workbook_id,
            workbook_name=self.name,
            reason=reason,
        )
        self.event_bus.publish(event)
        self._emit_status_change(old_status, "CANCELLED")
        logger.info("Workbook %s cancelled: %s", self.name, reason)
        return event

    def create_job(
        self,
        index: str,
        client: Elasticsearch,
        *,
        task_id: str = "",
        pause: float = 9.0,
        timeout: float = 7200.0,
    ) -> Job:
        """Create a new job for this workbook.

        Args:
            index: Index name for the job. Must be a non-empty string.
            client: Elasticsearch client forwarded to the Job and its Steps.
            task_id: Optional ES task id for ES-driven jobs.
            pause: Seconds between polling iterations (ES-driven mode).
            timeout: Maximum seconds to wait (ES-driven mode).

        Returns:
            New Job instance.

        Raises:
            ValueError: If index is empty.
        """
        if not index.strip():
            raise ValueError("index must be a non-empty string")

        job_id = f"{self.name}-{index}"
        job = Job(
            self.event_bus,
            self.tracking_index,
            job_id,
            self.name,
            index,
            client,
            task_id=task_id,
            pause=pause,
            timeout=timeout,
        )
        self.jobs.append(job)
        logger.debug("Created job %s for workbook %s", job_id, self.name)
        return job

    def get_history(self) -> list[dict[str, Any]]:
        """Get workbook history.

        Returns:
            List of history entries.
        """
        return self._history

    def _emit_status_change(self, old_status: str, new_status: str) -> None:
        """Emit a StatusChanged event.

        Args:
            old_status: Previous status.
            new_status: New status.
        """
        event = StatusChanged(
            entity_type="Workbook",
            entity_id=self.workbook_id,
            old_status=old_status,
            new_status=new_status,
        )
        self.event_bus.publish(event)

    def __repr__(self) -> str:
        return f"Workbook(name={self.name!r}, status={self.status!r}, jobs={len(self.jobs)})"
