"""Event types for es_tools.checkpoint event-driven architecture.

All events are dataclasses with immutable fields. Events are published by
entities (Workbook, Job, Step) on state changes and consumed by subscribers
(ElasticsearchBackend, IndexManager, LifecycleManager).
"""

from __future__ import annotations

import dataclasses
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BaseEvent:
    """Base class for all checkpoint events."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary."""
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Workbook Events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkbookStarted(BaseEvent):
    """Emitted when a Workbook transitions to RUNNING state."""

    workbook_id: str = ""
    workbook_name: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False


@dataclass(frozen=True)
class WorkbookCompleted(BaseEvent):
    """Emitted when a Workbook finishes successfully."""

    workbook_id: str = ""
    workbook_name: str = ""
    results: list[Any] = field(default_factory=list)


@dataclass(frozen=True)
class WorkbookCancelled(BaseEvent):
    """Emitted when a Workbook is cancelled."""

    workbook_id: str = ""
    workbook_name: str = ""
    reason: str = ""


@dataclass(frozen=True)
class WorkbookPaused(BaseEvent):
    """Emitted when a Workbook is paused."""

    workbook_id: str = ""
    workbook_name: str = ""


@dataclass(frozen=True)
class WorkbookResumed(BaseEvent):
    """Emitted when a paused Workbook is resumed."""

    workbook_id: str = ""
    workbook_name: str = ""


# ---------------------------------------------------------------------------
# Job Events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JobStarted(BaseEvent):
    """Emitted when a Job transitions to RUNNING state."""

    job_id: str = ""
    workbook_id: str = ""
    index: str = ""


@dataclass(frozen=True)
class JobCompleted(BaseEvent):
    """Emitted when a Job finishes successfully."""

    job_id: str = ""
    workbook_id: str = ""


@dataclass(frozen=True)
class JobFailed(BaseEvent):
    """Emitted when a Job fails."""

    job_id: str = ""
    workbook_id: str = ""
    error: str = ""


@dataclass(frozen=True)
class JobPaused(BaseEvent):
    """Emitted when a Job is paused."""

    job_id: str = ""
    workbook_id: str = ""


@dataclass(frozen=True)
class JobResumed(BaseEvent):
    """Emitted when a paused Job is resumed."""

    job_id: str = ""
    workbook_id: str = ""


# ---------------------------------------------------------------------------
# Step Events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepStarted(BaseEvent):
    """Emitted when a Step transitions to RUNNING state."""

    step_id: str = ""
    job_id: str = ""
    step_name: str = ""


@dataclass(frozen=True)
class Progress(BaseEvent):
    """In-step progress. Not a Step row; not journaled."""

    job_id: str = ""
    step_name: str = ""
    index: str = ""
    iteration: int = 0
    hits: int = 0


@dataclass(frozen=True)
class StepCompleted(BaseEvent):
    """Emitted when a Step finishes successfully."""

    step_id: str = ""
    job_id: str = ""


@dataclass(frozen=True)
class StepFailed(BaseEvent):
    """Emitted when a Step fails."""

    step_id: str = ""
    job_id: str = ""
    error: str = ""


@dataclass(frozen=True)
class StepPaused(BaseEvent):
    """Emitted when a Step is paused."""

    step_id: str = ""
    job_id: str = ""


@dataclass(frozen=True)
class StepResumed(BaseEvent):
    """Emitted when a paused Step is resumed."""

    step_id: str = ""
    job_id: str = ""


# ---------------------------------------------------------------------------
# Generic Events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StatusChanged(BaseEvent):
    """Emitted whenever any entity's status changes."""

    entity_type: str = ""
    entity_id: str = ""
    old_status: str = ""
    new_status: str = ""


@dataclass(frozen=True)
class ErrorOccurred(BaseEvent):
    """Emitted when an error occurs during any operation."""

    entity_type: str = ""
    entity_id: str = ""
    error: str = ""
    traceback_str: str = ""

    @classmethod
    def from_exception(
        cls,
        entity_type: str,
        entity_id: str,
        exc: Exception,
    ) -> ErrorOccurred:
        """Create an ErrorOccurred event from an exception."""
        return cls(
            entity_type=entity_type,
            entity_id=entity_id,
            error=str(exc),
            traceback_str=traceback.format_exc(),
        )


# ---------------------------------------------------------------------------
# Event type registry
# ---------------------------------------------------------------------------

EVENT_TYPES: tuple[type[BaseEvent], ...] = (
    WorkbookStarted,
    WorkbookCompleted,
    WorkbookCancelled,
    WorkbookPaused,
    WorkbookResumed,
    JobStarted,
    JobCompleted,
    JobFailed,
    JobPaused,
    JobResumed,
    StepStarted,
    StepCompleted,
    StepFailed,
    StepPaused,
    StepResumed,
    StatusChanged,
    ErrorOccurred,
)
