"""Unit tests for es_tools.checkpoint module."""

from unittest.mock import MagicMock, patch

import pytest

from es_tools.checkpoint import EventBus, Job, Step, Workbook


class TestWorkbook:
    """Test Workbook class."""

    def test_workbook_creation(self):
        """Test creating a Workbook instance."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        assert wb is not None
        assert wb.name == "test_workbook"

    def test_workbook_start(self):
        """Test starting a Workbook."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        event = wb.start()
        assert wb.status == "RUNNING"
        assert event.workbook_name == "test_workbook"

    def test_workbook_create_job(self):
        """Test creating a job within a workbook."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        assert job is not None
        assert job.index == "test_index"
        assert job in wb.jobs

    def test_workbook_lifecycle(self):
        """Test full workbook lifecycle: start -> pause -> resume -> complete."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})

        wb.start()
        assert wb.status == "RUNNING"

        wb.pause()
        assert wb.status == "PAUSED"

        wb.resume()
        assert wb.status == "RUNNING"

        wb.complete()
        assert wb.status == "COMPLETED"

    def test_workbook_cancel(self):
        """Test cancelling a Workbook."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        wb.start()
        event = wb.cancel()
        assert wb.status == "CANCELLED"
        assert event.workbook_name == "test_workbook"


class TestJob:
    """Test Job class."""

    def test_job_creation(self):
        """Test creating a Job instance."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        assert job is not None
        assert job.workbook_name == "test_workbook"
        assert job.index == "test_index"

    def test_job_start(self):
        """Test starting a Job."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        event = job.start()
        assert job.status == "RUNNING"
        assert event.job_id == job.doc_id

    def test_job_lifecycle(self):
        """Test full job lifecycle: start -> pause -> resume -> complete."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())

        job.start()
        assert job.status == "RUNNING"

        job.pause()
        assert job.status == "PAUSED"

        job.resume()
        assert job.status == "RUNNING"

        job.complete()
        assert job.status == "COMPLETED"

    def test_job_fail(self):
        """Test job failure."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        job.start()
        event = job.fail("something went wrong")
        assert job.status == "FAILED"
        assert event.error == "something went wrong"

    def test_job_requires_client(self) -> None:
        """Job.client is a required positional argument."""
        bus = EventBus()
        client = MagicMock()
        job = Job(bus, "test_index", "j1", "wb1", "idx", client)
        assert job.client is client

    def test_es_driven_sleeps_poll_pause_not_pause_method(self) -> None:
        """Monitoring loop must sleep the float, not Job.pause."""
        client = MagicMock()
        client.tasks.get.side_effect = [
            MagicMock(completed=False),
            MagicMock(completed=True),
        ]
        job = Job(
            EventBus(),
            "es-checkpoint",
            "j1",
            "wb1",
            "idx",
            client,
            task_id="abc",
            pause=1.5,
        )
        with patch("es_tools.checkpoint.job.time.sleep") as slept:
            job.start()
        slept.assert_called_with(1.5)
        assert job.status == "COMPLETED"

    def test_create_step_rejects_number_below_one(self) -> None:
        """Step numbers are 1-based."""
        job = Job(EventBus(), "es-checkpoint", "j1", "wb1", "idx", MagicMock())
        with pytest.raises(ValueError, match="number"):
            job.create_step(0, "x")

    def test_create_step_forwards_job_client(self) -> None:
        """Steps inherit the job client; they do not invent one."""
        client = MagicMock()
        job = Job(EventBus(), "es-checkpoint", "j1", "wb1", "idx", client)
        step = job.create_step(1, "resolve_index")
        assert step.client is client


class TestStep:
    """Test Step class."""

    def test_step_creation(self):
        """Test creating a Step instance."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        step = job.create_step(number=1, name="resolve_index")
        assert step is not None
        assert step.job_name == job.doc_id
        assert step.number == 1
        assert step.name == "resolve_index"

    def test_step_lifecycle(self):
        """Test full step lifecycle."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        step = job.create_step(number=1, name="resolve_index")

        assert step.status == "PENDING"
        step.start()
        assert step.status == "RUNNING"
        step.complete()
        assert step.status == "COMPLETED"

    def test_step_fail(self):
        """Test step failure."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        step = job.create_step(number=1, name="resolve_index")
        step.start()
        event = step.fail("step error")
        assert step.status == "FAILED"
        assert event.error == "step error"

    def test_step_ilm_phase_uses_check_index(self):
        """ilm_phase needs check_index (index) and check_value (phase)."""
        client = MagicMock()
        client.ilm.explain_lifecycle.return_value = {
            "indices": {"idx": {"managed": True, "phase": "cold", "step": "complete"}}
        }
        step = Step(
            EventBus(),
            "es-checkpoint",
            "s1",
            "job1",
            1,
            "wait-ilm",
            client,
            check_type="ilm_phase",
            check_value="cold",
            check_index="idx",
        )
        assert step._check_state() is True
        client.ilm.explain_lifecycle.assert_called_with(index="idx")

    def test_step_ilm_phase_without_check_index_is_not_done(self):
        """Missing check_index does not call ES (the old check_value-as-index wart)."""
        client = MagicMock()
        step = Step(
            EventBus(),
            "es-checkpoint",
            "s1",
            "job1",
            1,
            "wait-ilm",
            client,
            check_type="ilm_phase",
            check_value="cold",
        )
        assert step._check_state() is False
        client.ilm.explain_lifecycle.assert_not_called()

    def test_job_create_step_forwards_check_index(self):
        """Job.create_step passes check_index through to Step."""
        bus = EventBus()
        wb = Workbook(bus, "test_index", "test_workbook", {})
        job = wb.create_job("test_index", MagicMock())
        step = job.create_step(
            number=1,
            name="wait-ilm",
            check_type="ilm_phase",
            check_value="cold",
            check_index="idx",
        )
        assert step.check_index == "idx"
        assert step.check_value == "cold"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
