"""Unit tests for es_tools.checkpoint event system."""

from datetime import UTC, datetime

import pytest

from es_tools.checkpoint.events import (
    BaseEvent,
    ErrorOccurred,
    JobCompleted,
    JobFailed,
    JobPaused,
    JobResumed,
    JobStarted,
    Progress,
    StatusChanged,
    StepCompleted,
    StepFailed,
    StepPaused,
    StepResumed,
    StepStarted,
    WorkbookCancelled,
    WorkbookCompleted,
    WorkbookPaused,
    WorkbookResumed,
    WorkbookStarted,
)


class TestBaseEvent:
    """Test BaseEvent class."""

    def test_base_event_to_dict(self):
        """Test BaseEvent serialization."""
        event = BaseEvent()
        d = event.to_dict()
        assert "timestamp" in d
        assert isinstance(d["timestamp"], datetime)

    def test_base_event_timestamp(self):
        """Test BaseEvent timestamp."""
        event = BaseEvent()
        assert event.timestamp is not None
        assert event.timestamp.tzinfo is UTC


class TestWorkbookEvents:
    """Test Workbook events."""

    def test_workbook_started(self):
        """Test WorkbookStarted event."""
        event = WorkbookStarted(
            workbook_id="wb1",
            workbook_name="test_workbook",
            config={"key": "value"},
        )
        assert event.workbook_id == "wb1"
        assert event.workbook_name == "test_workbook"
        assert event.config == {"key": "value"}

    def test_workbook_completed(self):
        """Test WorkbookCompleted event."""
        event = WorkbookCompleted(
            workbook_id="wb1",
            workbook_name="test_workbook",
            results=["result1", "result2"],
        )
        assert event.workbook_id == "wb1"
        assert event.results == ["result1", "result2"]

    def test_workbook_cancelled(self):
        """Test WorkbookCancelled event."""
        event = WorkbookCancelled(
            workbook_id="wb1",
            workbook_name="test_workbook",
            reason="user requested",
        )
        assert event.workbook_id == "wb1"
        assert event.reason == "user requested"

    def test_workbook_paused(self):
        """Test WorkbookPaused event."""
        event = WorkbookPaused(
            workbook_id="wb1",
            workbook_name="test_workbook",
        )
        assert event.workbook_id == "wb1"

    def test_workbook_resumed(self):
        """Test WorkbookResumed event."""
        event = WorkbookResumed(
            workbook_id="wb1",
            workbook_name="test_workbook",
        )
        assert event.workbook_id == "wb1"


class TestJobEvents:
    """Test Job events."""

    def test_job_started(self):
        """Test JobStarted event."""
        event = JobStarted(
            job_id="job1",
            workbook_id="wb1",
            index="test_index",
        )
        assert event.job_id == "job1"
        assert event.workbook_id == "wb1"
        assert event.index == "test_index"

    def test_job_completed(self):
        """Test JobCompleted event."""
        event = JobCompleted(
            job_id="job1",
            workbook_id="wb1",
        )
        assert event.job_id == "job1"
        assert event.workbook_id == "wb1"

    def test_job_failed(self):
        """Test JobFailed event."""
        event = JobFailed(
            job_id="job1",
            workbook_id="wb1",
            error="something went wrong",
        )
        assert event.job_id == "job1"
        assert event.error == "something went wrong"

    def test_job_paused(self):
        """Test JobPaused event."""
        event = JobPaused(
            job_id="job1",
            workbook_id="wb1",
        )
        assert event.job_id == "job1"

    def test_job_resumed(self):
        """Test JobResumed event."""
        event = JobResumed(
            job_id="job1",
            workbook_id="wb1",
        )
        assert event.job_id == "job1"


class TestStepEvents:
    """Test Step events."""

    def test_step_started(self):
        """Test StepStarted event."""
        event = StepStarted(
            step_id="step1",
            job_id="job1",
            step_name="resolve_index",
        )
        assert event.step_id == "step1"
        assert event.job_id == "job1"
        assert event.step_name == "resolve_index"

    def test_progress(self):
        """Test Progress event."""
        event = Progress(
            job_id="job1",
            step_name="redact_fields",
            index="logs-1",
            iteration=2,
            hits=5,
        )
        assert event.index == "logs-1"
        assert event.iteration == 2
        assert event.hits == 5

    def test_step_completed(self):
        """Test StepCompleted event."""
        event = StepCompleted(
            step_id="step1",
            job_id="job1",
        )
        assert event.step_id == "step1"
        assert event.job_id == "job1"

    def test_step_failed(self):
        """Test StepFailed event."""
        event = StepFailed(
            step_id="step1",
            job_id="job1",
            error="step error",
        )
        assert event.step_id == "step1"
        assert event.error == "step error"

    def test_step_paused(self):
        """Test StepPaused event."""
        event = StepPaused(
            step_id="step1",
            job_id="job1",
        )
        assert event.step_id == "step1"

    def test_step_resumed(self):
        """Test StepResumed event."""
        event = StepResumed(
            step_id="step1",
            job_id="job1",
        )
        assert event.step_id == "step1"


class TestGenericEvents:
    """Test generic events."""

    def test_status_changed(self):
        """Test StatusChanged event."""
        event = StatusChanged(
            entity_type="Workbook",
            entity_id="wb1",
            old_status="PENDING",
            new_status="RUNNING",
        )
        assert event.entity_type == "Workbook"
        assert event.entity_id == "wb1"
        assert event.old_status == "PENDING"
        assert event.new_status == "RUNNING"

    def test_error_occurred(self):
        """Test ErrorOccurred event."""
        event = ErrorOccurred(
            entity_type="Job",
            entity_id="job1",
            error="test error",
            traceback_str="traceback...",
        )
        assert event.entity_type == "Job"
        assert event.entity_id == "job1"
        assert event.error == "test error"

    def test_error_from_exception(self):
        """Test ErrorOccurred.from_exception."""
        try:
            raise ValueError("test exception")
        except ValueError as exc:
            event = ErrorOccurred.from_exception("Job", "job1", exc)
            assert event.entity_type == "Job"
            assert event.entity_id == "job1"
            assert event.error == "test exception"
            assert "ValueError" in event.traceback_str
            assert "test exception" in event.traceback_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
