"""EventWaiter class for waiting on checkpoint events.

This module provides a waiter that subscribes to checkpoint events and resolves
when the expected event is received, rather than polling ES state.
"""

from __future__ import annotations

import logging
import time

from ..checkpoint.event_bus import EventBus
from ..checkpoint.events import BaseEvent

logger = logging.getLogger(__name__)


class EventWaiter:
    """Wait for a specific checkpoint event to fire.

    Instead of polling ES state, this waiter subscribes to the event bus and
    resolves when the expected event type is published. This is more efficient
    and works with any event type.

    Args:
        event_bus: Event bus to subscribe to.
        event_type: The event type to wait for.
        timeout: Maximum seconds to wait (default: 600).
        pause: Seconds between checks (default: 1.0).

    Example:
        >>> from es_tools.checkpoint import EventBus, JobStarted
        >>> bus = EventBus()
        >>> waiter = EventWaiter(bus, JobStarted, timeout=30)
        >>> waiter.wait()  # blocks until JobStarted event is published
    """

    def __init__(
        self,
        event_bus: EventBus,
        event_type: type[BaseEvent],
        timeout: float = 600.0,
        pause: float = 1.0,
    ):
        self.event_bus = event_bus
        self.event_type = event_type
        self.timeout = timeout
        self.pause = pause
        self._resolved = False
        self._event: BaseEvent | None = None

    def wait(self) -> bool:
        """Wait for the event to fire.

        Subscribes to the event bus and polls until the event is received
        or the timeout expires.

        Returns:
            True if the event was received before timeout, False otherwise.

        Raises:
            TimeoutError: If the event is not received within the timeout.
        """

        def on_event(event: BaseEvent) -> None:
            if isinstance(event, self.event_type):
                self._resolved = True
                self._event = event

        self.event_bus.subscribe(self.event_type, on_event)

        start_time = time.time()
        while not self._resolved:
            elapsed = time.time() - start_time
            if elapsed > self.timeout:
                raise TimeoutError(
                    f"EventWaiter timed out after {self.timeout}s "
                    f"waiting for {self.event_type.__name__}"
                )
            time.sleep(self.pause)

        return True

    @property
    def event(self) -> BaseEvent | None:
        """Get the received event, if any."""
        return self._event

    def __repr__(self) -> str:
        return (
            f"EventWaiter(event_type={self.event_type.__name__}, "
            f"resolved={self._resolved})"
        )
