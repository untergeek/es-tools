"""es_tools.checkpoint module.

Event-driven checkpoint system for tracking Elasticsearch operations.

Provides Workbook, Job, and Step classes with lifecycle management
(start/pause/resume/cancel), automatic persistence via event subscription,
and proper error handling.

Example:
    >>> from es_tools.checkpoint import Workbook
    >>> from es_tools.checkpoint.event_bus import EventBus
    >>> bus = EventBus()
    >>> wb = Workbook(bus, "es-checkpoint", "test_workbook", {"pattern": "*"})
    >>> wb.start()
    WorkbookStarted(workbook_id="test_workbook", ...)
"""

from .action_run import ActionRun, ExecuteResult, StepSpec
from .event_bus import EventBus
from .events import (
    BaseEvent,
    ErrorOccurred,
    JobFailed,
    JobPaused,
    JobResumed,
    JobStarted,
    Progress,
    StatusChanged,
    StepCompleted,
    StepFailed,
    StepStarted,
    WorkbookCancelled,
    WorkbookCompleted,
    WorkbookPaused,
    WorkbookResumed,
    WorkbookStarted,
)
from .index_manager import IndexManager
from .job import Job
from .step import Step
from .storage import ElasticsearchBackend
from .workbook import Workbook

__all__ = [
    "ActionRun",
    "BaseEvent",
    "ElasticsearchBackend",
    "ErrorOccurred",
    "EventBus",
    "ExecuteResult",
    "IndexManager",
    "Job",
    "JobFailed",
    "JobPaused",
    "JobResumed",
    "JobStarted",
    "Progress",
    "StatusChanged",
    "Step",
    "StepCompleted",
    "StepFailed",
    "StepSpec",
    "StepStarted",
    "Workbook",
    "WorkbookCancelled",
    "WorkbookCompleted",
    "WorkbookPaused",
    "WorkbookResumed",
    "WorkbookStarted",
]
