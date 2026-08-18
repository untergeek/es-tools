"""Unit tests for es_tools.checkpoint lifecycle management."""

from unittest.mock import MagicMock

import pytest

from es_tools.checkpoint import EventBus, Workbook
from es_tools.checkpoint.events import (
    JobCompleted,
    JobFailed,
    JobPaused,
    JobResumed,
    JobStarted,
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


class TestWorkbookLifecycle:
    """Test Workbook lifecycle."""

    def test_workbook_start(self):
        """Test starting a workbook."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        event = wb.start()
        assert wb.status == "RUNNING"
        assert isinstance(event, WorkbookStarted)
        assert event.workbook_name == "test_workbook"

    def test_workbook_started_stamps_dry_run(self) -> None:
        """dry_run is copied onto the event and published config, not the caller dict."""
        bus = EventBus()
        cfg = {"action": "close"}
        wb = Workbook(bus, "test_index", "wb-dry", cfg, dry_run=True)
        event = wb.start()
        assert event.dry_run is True
        assert event.config["dry_run"] is True
        assert event.config["action"] == "close"
        assert "dry_run" not in cfg

    def test_workbook_started_dry_run_false_is_explicit(self) -> None:
        """Live runs stamp dry_run False so the field is always queryable."""
        bus = EventBus()
        event = Workbook(bus, "test_index", "wb-live", {}, dry_run=False).start()
        assert event.dry_run is False
        assert event.config["dry_run"] is False

    def test_workbook_pause(self):
        """Test pausing a workbook."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        wb.start()
        event = wb.pause()
        assert wb.status == "PAUSED"
        assert isinstance(event, WorkbookPaused)

    def test_workbook_resume(self):
        """Test resuming a paused workbook."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        wb.start()
        wb.pause()
        event = wb.resume()
        assert wb.status == "RUNNING"
        assert isinstance(event, WorkbookResumed)

    def test_workbook_complete(self):
        """Test completing a workbook."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        wb.start()
        event = wb.complete()
        assert wb.status == "COMPLETED"
        assert isinstance(event, WorkbookCompleted)

    def test_workbook_cancel(self):
        """Test cancelling a workbook."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        wb.start()
        event = wb.cancel()
        assert wb.status == "CANCELLED"
        assert isinstance(event, WorkbookCancelled)

    def test_workbook_status_changes(self):
        """Test that status changes emit StatusChanged events."""
        bus = EventBus()
        status_changes = []

        def on_status_change(event):
            if isinstance(event, StatusChanged):
                status_changes.append(event)

        bus.subscribe(StatusChanged, on_status_change)

        wb = Workbook(bus, "test_index", "test_workbook", {})
        wb.start()
        wb.pause()
        wb.resume()
        wb.complete()

        assert len(status_changes) == 4
        assert status_changes[0].old_status == "PENDING"
        assert status_changes[0].new_status == "RUNNING"
        assert status_changes[1].old_status == "RUNNING"
        assert status_changes[1].new_status == "PAUSED"
        assert status_changes[2].old_status == "PAUSED"
        assert status_changes[2].new_status == "RUNNING"
        assert status_changes[3].old_status == "RUNNING"
        assert status_changes[3].new_status == "COMPLETED"


class TestJobLifecycle:
    """Test Job lifecycle."""

    def test_job_start(self):
        """Test starting a job."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        event = job.start()
        assert job.status == "RUNNING"
        assert isinstance(event, JobStarted)
        assert event.job_id == job.doc_id

    def test_job_pause(self):
        """Test pausing a job."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        job.start()
        event = job.pause()
        assert job.status == "PAUSED"
        assert isinstance(event, JobPaused)

    def test_job_resume(self):
        """Test resuming a paused job."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        job.start()
        job.pause()
        event = job.resume()
        assert job.status == "RUNNING"
        assert isinstance(event, JobResumed)

    def test_job_complete(self):
        """Test completing a job."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        job.start()
        event = job.complete()
        assert job.status == "COMPLETED"
        assert isinstance(event, JobCompleted)

    def test_job_fail(self):
        """Test failing a job."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        job.start()
        event = job.fail("test error")
        assert job.status == "FAILED"
        assert isinstance(event, JobFailed)
        assert event.error == "test error"

    def test_job_status_changes(self):
        """Test that job status changes emit StatusChanged events."""
        bus = EventBus()
        status_changes = []

        def on_status_change(event):
            if isinstance(event, StatusChanged):
                status_changes.append(event)

        bus.subscribe(StatusChanged, on_status_change)

        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        job.start()
        job.pause()
        job.resume()
        job.complete()

        assert len(status_changes) == 4
        assert status_changes[0].entity_type == "Job"
        assert status_changes[0].old_status == "PENDING"
        assert status_changes[0].new_status == "RUNNING"


class TestStepLifecycle:
    """Test Step lifecycle."""

    def test_step_start(self):
        """Test starting a step."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        step = job.create_step(number=1, name="resolve_index")
        event = step.start()
        assert step.status == "RUNNING"
        assert isinstance(event, StepStarted)
        assert event.step_id == step.doc_id

    def test_step_complete(self):
        """Test completing a step."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        step = job.create_step(number=1, name="resolve_index")
        step.start()
        event = step.complete()
        assert step.status == "COMPLETED"
        assert isinstance(event, StepCompleted)

    def test_step_fail(self):
        """Test failing a step."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        step = job.create_step(number=1, name="resolve_index")
        step.start()
        event = step.fail("test error")
        assert step.status == "FAILED"
        assert isinstance(event, StepFailed)
        assert event.error == "test error"

    def test_step_status_changes(self):
        """Test that step status changes emit StatusChanged events."""
        bus = EventBus()
        status_changes = []

        def on_status_change(event):
            if isinstance(event, StatusChanged):
                status_changes.append(event)

        bus.subscribe(StatusChanged, on_status_change)

        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        step = job.create_step(number=1, name="resolve_index")
        step.start()
        step.complete()

        assert len(status_changes) == 2
        assert status_changes[0].entity_type == "Step"
        assert status_changes[0].old_status == "PENDING"
        assert status_changes[0].new_status == "RUNNING"
        assert status_changes[1].old_status == "RUNNING"
        assert status_changes[1].new_status == "COMPLETED"


class TestEventEmission:
    """Test event emission on state changes."""

    def test_workbook_events(self):
        """Test that workbook emits correct events."""
        bus = EventBus()
        events = []

        def on_event(event):
            events.append(event)

        bus.subscribe(WorkbookStarted, on_event)
        bus.subscribe(WorkbookCompleted, on_event)
        bus.subscribe(WorkbookCancelled, on_event)

        wb = Workbook(bus, "test_index", "test_workbook", {})
        wb.start()
        wb.cancel()

        assert len(events) == 2
        assert isinstance(events[0], WorkbookStarted)
        assert isinstance(events[1], WorkbookCancelled)

    def test_job_events(self):
        """Test that job emits correct events."""
        bus = EventBus()
        events = []

        def on_event(event):
            events.append(event)

        bus.subscribe(JobStarted, on_event)
        bus.subscribe(JobCompleted, on_event)
        bus.subscribe(JobFailed, on_event)

        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        job.start()
        job.fail("test error")

        assert len(events) == 2
        assert isinstance(events[0], JobStarted)
        assert isinstance(events[1], JobFailed)

    def test_step_events(self):
        """Test that step emits correct events."""
        bus = EventBus()
        events = []

        def on_event(event):
            events.append(event)

        bus.subscribe(StepStarted, on_event)
        bus.subscribe(StepCompleted, on_event)
        bus.subscribe(StepFailed, on_event)

        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        step = job.create_step(number=1, name="resolve_index")
        step.start()
        step.fail("test error")

        assert len(events) == 2
        assert isinstance(events[0], StepStarted)
        assert isinstance(events[1], StepFailed)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
