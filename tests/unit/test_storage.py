"""Unit tests for es_tools.checkpoint storage backend."""

from unittest.mock import Mock

import pytest

from es_tools.checkpoint import EventBus
from es_tools.checkpoint.events import (
    JobFailed,
    StepCompleted,
    WorkbookStarted,
)
from es_tools.checkpoint.storage import ElasticsearchBackend


class TestElasticsearchBackend:
    """Test ElasticsearchBackend class."""

    def test_backend_creation(self):
        """Test creating an ElasticsearchBackend instance."""
        client = Mock()
        bus = EventBus()
        backend = ElasticsearchBackend(client, bus, "test_index")
        assert backend is not None
        assert backend.client == client
        assert backend.tracking_index == "test_index"

    def test_backend_does_not_subscribe_to_progress(self) -> None:
        """Progress is in-process only; not journaled."""
        from es_tools.checkpoint.events import Progress

        client = Mock()
        bus = EventBus()
        ElasticsearchBackend(client, bus, "test_index")
        assert Progress not in bus._subscribers

    def test_backend_subscribes_to_events(self):
        """Test that backend subscribes to all event types."""
        client = Mock()
        bus = EventBus()
        ElasticsearchBackend(client, bus, "test_index")

        # Check that subscriptions were created
        assert len(bus._subscribers) > 0

    def test_backend_persists_workbook_started(self):
        """Test that backend persists WorkbookStarted event."""
        client = Mock()
        bus = EventBus()
        backend = ElasticsearchBackend(client, bus, "test_index")

        event = WorkbookStarted(
            workbook_id="wb1",
            workbook_name="test_workbook",
            config={"key": "value"},
        )
        backend._on_workbook_started(event)

        client.index.assert_called_once()
        doc = client.index.call_args[1]["document"]
        assert doc["workbook_id"] == "wb1"
        assert doc["workbook_name"] == "test_workbook"
        assert doc["status"] == "RUNNING"
        assert doc["dry_run"] is False

    def test_backend_indexes_dry_run_top_level(self) -> None:
        """Tracking docs carry top-level dry_run for filter queries."""
        client = Mock()
        bus = EventBus()
        backend = ElasticsearchBackend(client, bus, "test_index")
        event = WorkbookStarted(
            workbook_id="wb1",
            workbook_name="dry",
            config={"action": "close", "dry_run": True},
            dry_run=True,
        )
        backend._on_workbook_started(event)
        doc = client.index.call_args[1]["document"]
        assert doc["dry_run"] is True
        assert doc["config"]["dry_run"] is True

    def test_backend_persists_job_failed(self):
        """Test that backend persists JobFailed event."""
        client = Mock()
        bus = EventBus()
        backend = ElasticsearchBackend(client, bus, "test_index")

        event = JobFailed(
            job_id="job1",
            workbook_id="wb1",
            error="test error",
        )
        backend._on_job_failed(event)

        client.index.assert_called_once()
        doc = client.index.call_args[1]["document"]
        assert doc["job_id"] == "job1"
        assert doc["workbook_id"] == "wb1"
        assert doc["status"] == "FAILED"
        assert doc["error"] == "test error"

    def test_backend_persists_step_completed(self):
        """Test that backend persists StepCompleted event."""
        client = Mock()
        bus = EventBus()
        backend = ElasticsearchBackend(client, bus, "test_index")

        event = StepCompleted(
            step_id="step1",
            job_id="job1",
        )
        backend._on_step_completed(event)

        client.index.assert_called_once()
        doc = client.index.call_args[1]["document"]
        assert doc["step_id"] == "step1"
        assert doc["job_id"] == "job1"
        assert doc["status"] == "COMPLETED"

    def test_backend_get_workbook_history(self):
        """Test getting workbook history."""
        client = Mock()
        client.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"workbook_id": "wb1", "status": "RUNNING"}},
                    {"_source": {"workbook_id": "wb1", "status": "COMPLETED"}},
                ]
            }
        }
        bus = EventBus()
        backend = ElasticsearchBackend(client, bus, "test_index")

        history = backend.get_workbook_history("wb1")
        assert len(history) == 2
        assert history[0]["status"] == "RUNNING"
        assert history[1]["status"] == "COMPLETED"

    def test_backend_get_job_history(self):
        """Test getting job history."""
        client = Mock()
        client.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"job_id": "job1", "status": "RUNNING"}},
                    {"_source": {"job_id": "job1", "status": "COMPLETED"}},
                ]
            }
        }
        bus = EventBus()
        backend = ElasticsearchBackend(client, bus, "test_index")

        history = backend.get_job_history("job1")
        assert len(history) == 2
        assert history[0]["status"] == "RUNNING"
        assert history[1]["status"] == "COMPLETED"

    def test_backend_get_step_status(self):
        """Test getting step status."""
        client = Mock()
        client.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"step_id": "step1", "status": "COMPLETED"}},
                ]
            }
        }
        bus = EventBus()
        backend = ElasticsearchBackend(client, bus, "test_index")

        status = backend.get_step_status("step1")
        assert status is not None
        assert status["status"] == "COMPLETED"

    def test_backend_error_handling(self):
        """Test error handling in backend."""
        client = Mock()
        client.index.side_effect = Exception("Indexing failed")
        bus = EventBus()
        backend = ElasticsearchBackend(client, bus, "test_index")

        event = WorkbookStarted(
            workbook_id="wb1",
            workbook_name="test_workbook",
        )

        with pytest.raises(Exception, match="Indexing failed"):
            backend._on_workbook_started(event)

    def test_backend_creates_date_mapping_and_at_timestamp(self) -> None:
        """New tracking index gets date mappings; docs copy @timestamp."""
        client = Mock()
        client.indices.exists.return_value = False
        bus = EventBus()
        backend = ElasticsearchBackend(client, bus, "test_index")
        event = WorkbookStarted(
            workbook_id="wb1",
            workbook_name="test_workbook",
        )
        backend._on_workbook_started(event)
        client.indices.exists.assert_called_once_with(index="test_index")
        client.indices.create.assert_called_once()
        mappings = client.indices.create.call_args.kwargs["mappings"]
        props = mappings["properties"]
        assert props["timestamp"] == {"type": "date"}
        assert props["@timestamp"] == {"type": "date"}
        doc = client.index.call_args.kwargs["document"]
        assert doc["@timestamp"] == doc["timestamp"]
        assert isinstance(doc["timestamp"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
