"""Index manager for event-driven checkpoint.

Handles creation and deletion of tracking indices based on checkpoint events.
"""

from __future__ import annotations

import logging
from typing import Any

from .event_bus import EventBus
from .events import BaseEvent, WorkbookCancelled, WorkbookStarted

logger = logging.getLogger(__name__)


class IndexManager:
    """Manages tracking indices based on checkpoint events.

    Automatically creates indices when workbooks start and can delete them
    when workbooks are cancelled (optional, based on configuration).

    Args:
        client: Elasticsearch client instance.
        event_bus: Event bus to subscribe to events.
        auto_delete: If True, delete indices when workbooks are cancelled.

    Example:
        >>> from elasticsearch9 import Elasticsearch
        >>> from es_tools.checkpoint.event_bus import EventBus
        >>> client = Elasticsearch()
        >>> bus = EventBus()
        >>> manager = IndexManager(client, bus, auto_delete=False)
        >>> manager._on_workbook_started(WorkbookStarted(workbook_id="1", workbook_name="test"))
    """

    def __init__(
        self,
        client: Any,
        event_bus: EventBus,
        auto_delete: bool = False,
    ) -> None:
        self.client = client
        self.event_bus = event_bus
        self.auto_delete = auto_delete

        # Subscribe to relevant events
        self.event_bus.subscribe(WorkbookStarted, self._on_workbook_started)
        if auto_delete:
            self.event_bus.subscribe(WorkbookCancelled, self._on_workbook_cancelled)

        logger.info("IndexManager initialized with auto_delete=%s", auto_delete)

    def _on_workbook_started(self, event: BaseEvent) -> None:
        """Handle WorkbookStarted event - create tracking index if needed."""
        assert isinstance(event, WorkbookStarted)
        tracking_index = f"es-checkpoint-{event.workbook_id}"
        self._create_index_if_not_exists(tracking_index)

    def _on_workbook_cancelled(self, event: BaseEvent) -> None:
        """Handle WorkbookCancelled event - delete tracking index if configured."""
        if self.auto_delete:
            assert isinstance(event, WorkbookCancelled)
            tracking_index = f"es-checkpoint-{event.workbook_id}"
            self._delete_index(tracking_index)

    def _create_index_if_not_exists(self, index_name: str) -> None:
        """Create an index if it doesn't already exist.

        Args:
            index_name: Index name to create.
        """
        try:
            if not self.client.indices.exists(index=index_name):
                self.client.indices.create(index=index_name)
                logger.info("Created index: %s", index_name)
            else:
                logger.debug("Index already exists: %s", index_name)
        except Exception as exc:
            logger.error("Failed to create index %s: %s", index_name, exc)

    def _delete_index(self, index_name: str) -> None:
        """Delete an index.

        Args:
            index_name: Index name to delete.
        """
        try:
            if self.client.indices.exists(index=index_name):
                self.client.indices.delete(index=index_name)
                logger.info("Deleted index: %s", index_name)
            else:
                logger.debug("Index does not exist: %s", index_name)
        except Exception as exc:
            logger.error("Failed to delete index %s: %s", index_name, exc)

    def create_index(self, index_name: str) -> None:
        """Manually create an index.

        Args:
            index_name: Index name to create.
        """
        self._create_index_if_not_exists(index_name)

    def delete_index(self, index_name: str) -> None:
        """Manually delete an index.

        Args:
            index_name: Index name to delete.
        """
        self._delete_index(index_name)
