"""Step class for event-driven checkpoint management.

Steps represent individual operations within a Job. They can be started,
completed, or failed, and emit events on state changes. Steps can be either
user-driven (manual lifecycle) or state-driven (monitoring ES state changes).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from .event_bus import EventBus
from .events import StatusChanged, StepCompleted, StepFailed, StepStarted

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from elasticsearch9 import Elasticsearch


class Step:
    """Step represents an individual operation within a Job.

    A Step can be either:

    - **User-driven**: manual lifecycle (start → complete/fail)
    - **State-driven**: monitors ES state changes (health, exists, relocate, ilm)

    Args:
        event_bus: Event bus for publishing events.
        tracking_index: Name of the tracking index.
        doc_id: Unique ID for the step.
        job_name: Name of the parent job.
        number: Step number.
        name: Step name.
        client: Elasticsearch client. Required; used by state-driven monitoring.
        check_type: Type of state to monitor (e.g., "health", "exists",
            "relocate", "ilm_phase", "ilm_step").
        check_value: Expected value for the state check (health status, index
            name, ILM phase, or ILM step).
        check_index: Index for ``ilm_phase`` / ``ilm_step``. Not the phase.
        pause: Seconds between polling iterations (state-driven mode).
        timeout: Maximum seconds to wait for completion (state-driven mode).

    Example (user-driven):
        >>> from es_tools.checkpoint.event_bus import EventBus
        >>> bus = EventBus()
        >>> step = Step(bus, "es-checkpoint", "job1-step-1", "job1", 1, "resolve_index", client)
        >>> step.start()
        StepStarted(step_id="job1-step-1", ...)

    Example (state-driven):
        >>> step = Step(bus, "es-checkpoint", "job1-step-1", "job1", 1, "wait_green",
        ...             client, check_type="health", check_value="green")
        >>> step.start()  # begins monitoring cluster health
        >>> step = Step(bus, "es-checkpoint", "job1-step-2", "job1", 2, "wait_cold",
        ...             client, check_type="ilm_phase", check_value="cold",
        ...             check_index="logs-000001")
    """

    def __init__(
        self,
        event_bus: EventBus,
        tracking_index: str,
        doc_id: str,
        job_name: str,
        number: int,
        name: str,
        client: Elasticsearch,
        check_type: str | None = None,
        check_value: str | None = None,
        check_index: str | None = None,
        pause: float = 1.0,
        timeout: float = 60.0,
    ) -> None:
        self.event_bus = event_bus
        self.tracking_index = tracking_index
        self.doc_id = doc_id
        self.job_name = job_name
        self.number = number
        self.name = name
        self.client: Elasticsearch = client
        self.check_type = check_type
        self.check_value = check_value
        self.check_index = check_index
        self.poll_pause = pause
        self.timeout = timeout
        self.status: str = "PENDING"
        self.created_at: datetime = datetime.now(UTC)
        self.updated_at: datetime = datetime.now(UTC)
        self._error: str | None = None

    def start(self) -> StepStarted:
        """Start the step.

        If ``check_type`` is provided, begins monitoring ES state
        (state-driven mode) and **blocks** until the poll loop finishes
        (success, fail, or timeout; default timeout 60s). ActionRun does
        not use this path; it waits via ``es_tools.wait``. Otherwise,
        emits a ``StepStarted`` event (user-driven mode) and returns
        immediately.

        Returns:
            StepStarted event.

        Raises:
            RuntimeError: If step is already running.
        """
        if self.status == "RUNNING":
            raise RuntimeError(f"Step {self.doc_id} is already running")

        old_status = self.status
        self.status = "RUNNING"
        self.updated_at = datetime.now(UTC)

        event = StepStarted(
            step_id=self.doc_id,
            job_id=self.job_name,
            step_name=self.name,
        )
        self.event_bus.publish(event)
        self._emit_status_change(old_status, "RUNNING")
        logger.info("Step %s started", self.doc_id)

        if self.check_type:
            self._start_monitoring()

        return event

    def _start_monitoring(self) -> None:
        """Poll ES state until the desired state is reached."""
        start_time = time.time()
        while self.status == "RUNNING":
            elapsed = time.time() - start_time
            if elapsed > self.timeout:
                self.fail(f"Step {self.doc_id} timed out after {self.timeout}s")
                return
            if self._check_state():
                self.complete()
                return
            time.sleep(self.poll_pause)

    def _check_state(self) -> bool:
        """Check ES state based on check_type and check_value.

        Returns:
            True if the desired state is reached, False otherwise.
        """
        if not self.check_type or not self.check_value:
            return False

        try:
            if self.check_type == "health":
                status = self.client.cluster.health()
                return status["status"] == self.check_value
            elif self.check_type == "exists":
                return bool(self.client.indices.exists(index=self.check_value))
            elif self.check_type == "relocate":
                health = self.client.cluster.health()
                relocating_shards = int(health.get("relocating_shards", 0))
                return relocating_shards == 0
            elif self.check_type == "ilm_phase":
                if not self.check_index:
                    return False
                from es_tools.wait.ilm import IlmPhase

                return IlmPhase(
                    self.client, index=self.check_index, phase=self.check_value
                ).check()
            elif self.check_type == "ilm_step":
                if not self.check_index:
                    return False
                from es_tools.wait.ilm import IlmStep

                return IlmStep(
                    self.client, index=self.check_index, step=self.check_value
                ).check()
            else:
                logger.warning("Unknown check_type: %s", self.check_type)
                return False
        except Exception as exc:
            logger.warning("Step %s: state check error: %s", self.doc_id, exc)
            return False

    def complete(self) -> StepCompleted:
        """Complete the step successfully and emit StepCompleted event.

        Returns:
            StepCompleted event.

        Raises:
            RuntimeError: If step is not running.
        """
        if self.status != "RUNNING":
            raise RuntimeError(
                f"Step {self.doc_id} is not running (status: {self.status})"
            )

        old_status = self.status
        self.status = "COMPLETED"
        self.updated_at = datetime.now(UTC)

        event = StepCompleted(
            step_id=self.doc_id,
            job_id=self.job_name,
        )
        self.event_bus.publish(event)
        self._emit_status_change(old_status, "COMPLETED")
        logger.info("Step %s completed", self.doc_id)
        return event

    def fail(self, error: str) -> StepFailed:
        """Fail the step and emit StepFailed event.

        Args:
            error: Error message.

        Returns:
            StepFailed event.

        Raises:
            RuntimeError: If step is not running.
        """
        if self.status != "RUNNING":
            raise RuntimeError(
                f"Step {self.doc_id} is not running (status: {self.status})"
            )

        old_status = self.status
        self.status = "FAILED"
        self.updated_at = datetime.now(UTC)
        self._error = error

        event = StepFailed(
            step_id=self.doc_id,
            job_id=self.job_name,
            error=error,
        )
        self.event_bus.publish(event)
        self._emit_status_change(old_status, "FAILED")
        logger.error("Step %s failed: %s", self.doc_id, error)
        return event

    def _emit_status_change(self, old_status: str, new_status: str) -> None:
        """Emit a StatusChanged event.

        Args:
            old_status: Previous status.
            new_status: New status.
        """
        event = StatusChanged(
            entity_type="Step",
            entity_id=self.doc_id,
            old_status=old_status,
            new_status=new_status,
        )
        self.event_bus.publish(event)

    def __repr__(self) -> str:
        return f"Step(job={self.job_name!r}, step={self.doc_id!r}, name={self.name!r})"
