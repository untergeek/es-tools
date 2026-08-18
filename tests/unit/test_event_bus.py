"""Unit tests for es_tools.checkpoint event bus."""

import pytest

from es_tools.checkpoint.event_bus import EventBus
from es_tools.checkpoint.events import (
    JobStarted,
    Progress,
    StepStarted,
    WorkbookStarted,
)


class TestEventBus:
    """Test EventBus class."""

    def test_event_bus_creation(self):
        """Test creating an EventBus instance."""
        bus = EventBus()
        assert bus is not None

    def test_subscribe_publish(self):
        """Test subscribing to and publishing events."""
        bus = EventBus()
        received_events = []

        def handler(event):
            received_events.append(event)

        bus.subscribe(WorkbookStarted, handler)
        event = WorkbookStarted(workbook_id="wb1", workbook_name="test")
        bus.publish(event)

        assert len(received_events) == 1
        assert received_events[0] == event

    def test_progress_subscribe_publish(self):
        """Progress events reach subscribers."""
        bus = EventBus()
        received = []
        bus.subscribe(Progress, received.append)
        event = Progress(index="logs-1", iteration=1, hits=3)
        bus.publish(event)
        assert received == [event]

    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        bus = EventBus()
        received_events = []

        def handler(event):
            received_events.append(event)

        bus.subscribe(WorkbookStarted, handler)
        bus.unsubscribe(WorkbookStarted, handler)

        event = WorkbookStarted(workbook_id="wb1", workbook_name="test")
        bus.publish(event)

        assert len(received_events) == 0

    def test_unsubscribe_missing_is_noop(self):
        """Unsubscribing a callback that was never subscribed is a no-op."""
        bus = EventBus()
        bus.unsubscribe(WorkbookStarted, lambda e: None)

    def test_partial_callback_does_not_crash_on_publish_error(self):
        """functools.partial subscribers must not AttributeError on __name__."""
        from functools import partial

        bus = EventBus()

        def boom(event, extra):
            raise RuntimeError("x")

        bus.subscribe(WorkbookStarted, partial(boom, extra=1))
        bus.publish(WorkbookStarted(workbook_id="w", workbook_name="n"))

    def test_clear(self):
        """Test clearing all subscriptions."""
        bus = EventBus()
        received_events = []

        def handler(event):
            received_events.append(event)

        bus.subscribe(WorkbookStarted, handler)
        bus.clear()

        event = WorkbookStarted(workbook_id="wb1", workbook_name="test")
        bus.publish(event)

        assert len(received_events) == 0

    def test_multiple_subscribers(self):
        """Test multiple subscribers for the same event."""
        bus = EventBus()
        received_events_1 = []
        received_events_2 = []

        def handler_1(event):
            received_events_1.append(event)

        def handler_2(event):
            received_events_2.append(event)

        bus.subscribe(WorkbookStarted, handler_1)
        bus.subscribe(WorkbookStarted, handler_2)

        event = WorkbookStarted(workbook_id="wb1", workbook_name="test")
        bus.publish(event)

        assert len(received_events_1) == 1
        assert len(received_events_2) == 1

    def test_event_filtering(self):
        """Test event filtering (subscribe to specific event types)."""
        bus = EventBus()
        received_events = []

        def handler(event):
            received_events.append(event)

        # Subscribe only to WorkbookStarted
        bus.subscribe(WorkbookStarted, handler)

        # Publish different event types
        bus.publish(WorkbookStarted(workbook_id="wb1", workbook_name="test"))
        bus.publish(JobStarted(job_id="job1", workbook_id="wb1", index="test"))
        bus.publish(StepStarted(step_id="step1", job_id="job1", step_name="test"))

        # Only WorkbookStarted should be received
        assert len(received_events) == 1
        assert isinstance(received_events[0], WorkbookStarted)

    def test_event_serialization(self):
        """Test event serialization via to_dict()."""
        event = WorkbookStarted(
            workbook_id="wb1",
            workbook_name="test_workbook",
            config={"key": "value"},
        )
        d = event.to_dict()
        assert d["workbook_id"] == "wb1"
        assert d["workbook_name"] == "test_workbook"
        assert d["config"] == {"key": "value"}
        assert "timestamp" in d


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
