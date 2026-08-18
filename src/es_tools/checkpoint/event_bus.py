"""Event bus for es_tools.checkpoint event-driven architecture.

Pub/sub event bus that allows entities to publish events and subscribers
to receive them. Supports type-safe event filtering and multiple subscribers
per event type.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from .events import BaseEvent

logger = logging.getLogger(__name__)


def _cb_name(callback: Callable[..., Any]) -> str:
    """Return a log-safe callback name (works for functools.partial)."""
    return getattr(callback, "__name__", repr(callback))


class EventBus:
    """Pub/sub event bus for checkpoint events.

    Supports:
    - Type-safe event publishing (only BaseEvent subclasses)
    - Multiple subscribers per event type
    - Event filtering (subscribe to specific event types)
    - Automatic cleanup on unsubscribe

    Example:
        >>> bus = EventBus()
        >>> bus.subscribe(JobStarted, lambda e: print(f"Job {e.job_name} started"))
        >>> bus.publish(JobStarted(job_id="1", job_name="test"))
        Job test started
    """

    def __init__(self) -> None:
        self._subscribers: dict[type[BaseEvent], list[Callable[[BaseEvent], None]]] = (
            defaultdict(list)
        )

    def subscribe(
        self,
        event_type: type[BaseEvent],
        callback: Callable[[BaseEvent], None],
    ) -> None:
        """Subscribe a callback to an event type.

        Args:
            event_type: The event type to subscribe to.
            callback: The callback function to call when the event is published.

        Raises:
            TypeError: If event_type is not a BaseEvent subclass.
        """
        if not issubclass(event_type, BaseEvent):
            raise TypeError(
                f"event_type must be a BaseEvent subclass, got {event_type}"
            )
        self._subscribers[event_type].append(callback)
        logger.debug("Subscribed %s to %s", _cb_name(callback), event_type.__name__)

    def unsubscribe(
        self,
        event_type: type[BaseEvent],
        callback: Callable[[BaseEvent], None],
    ) -> None:
        """Unsubscribe a callback from an event type.

        Args:
            event_type: The event type to unsubscribe from.
            callback: The callback function to remove.

        Missing callbacks are a no-op.
        """
        subs = self._subscribers.get(event_type, [])
        if callback not in subs:
            logger.debug(
                "Callback %s not subscribed to %s",
                _cb_name(callback),
                event_type.__name__,
            )
            return
        subs.remove(callback)
        logger.debug("Unsubscribed %s from %s", _cb_name(callback), event_type.__name__)

    def publish(self, event: BaseEvent) -> None:
        """Publish an event to all subscribers.

        Args:
            event: The event to publish.

        Raises:
            TypeError: If event is not a BaseEvent instance.
        """
        if not isinstance(event, BaseEvent):
            raise TypeError(f"event must be a BaseEvent instance, got {type(event)}")

        event_type = type(event)
        subscribers = self._subscribers.get(event_type, [])

        for callback in subscribers:
            try:
                callback(event)
            except Exception as exc:
                logger.error(
                    "Error in subscriber %s for event %s: %s",
                    _cb_name(callback),
                    event_type.__name__,
                    exc,
                )

    def clear(self) -> None:
        """Clear all subscribers."""
        self._subscribers.clear()
        logger.debug("Cleared all subscribers")

    def get_subscriber_count(self, event_type: type[BaseEvent]) -> int:
        """Get the number of subscribers for an event type.

        Args:
            event_type: The event type to check.

        Returns:
            Number of subscribers.
        """
        return len(self._subscribers.get(event_type, []))

    def has_subscribers(self, event_type: type[BaseEvent]) -> bool:
        """Check if an event type has any subscribers.

        Args:
            event_type: The event type to check.

        Returns:
            True if there are subscribers.
        """
        return len(self._subscribers.get(event_type, [])) > 0
