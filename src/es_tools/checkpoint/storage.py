"""Elasticsearch storage backend for event-driven checkpoint.

Subscribes to checkpoint events and automatically persists entity state
changes to Elasticsearch. Handles index creation/deletion based on events.
"""

from __future__ import annotations

import logging
from typing import Any

from .event_bus import EventBus
from .events import (
    BaseEvent,
    JobFailed,
    JobPaused,
    JobResumed,
    JobStarted,
    StepCompleted,
    StepFailed,
    StepStarted,
    WorkbookCancelled,
    WorkbookCompleted,
    WorkbookPaused,
    WorkbookResumed,
    WorkbookStarted,
)

logger = logging.getLogger(__name__)

TRACKING_DATE_MAPPING: dict[str, Any] = {
    "properties": {
        "timestamp": {"type": "date"},
        "@timestamp": {"type": "date"},
    }
}


class ElasticsearchBackend:
    """Elasticsearch storage backend that subscribes to checkpoint events.

    Automatically persists entity state changes to Elasticsearch by
    subscribing to relevant events from the EventBus.

    Args:
        client: Elasticsearch client instance.
        event_bus: Event bus to subscribe to events.
        tracking_index: Name of the tracking index (default: "es-checkpoint").

    Example:
        >>> from elasticsearch9 import Elasticsearch
        >>> from es_tools.checkpoint.event_bus import EventBus
        >>> client = Elasticsearch()
        >>> bus = EventBus()
        >>> backend = ElasticsearchBackend(client, bus, "es-checkpoint")
        >>> backend._on_workbook_started(WorkbookStarted(workbook_id="1", workbook_name="test"))
    """

    def __init__(
        self,
        client: Any,
        event_bus: EventBus,
        tracking_index: str = "es-checkpoint",
    ) -> None:
        self.client = client
        self.event_bus = event_bus
        self.tracking_index = tracking_index
        self._index_ready = False

        # Subscribe to all relevant events
        self._subscribe_to_events()
        logger.info(
            "ElasticsearchBackend initialized with tracking_index=%s",
            tracking_index,
        )

    def _subscribe_to_events(self) -> None:
        """Subscribe to all relevant checkpoint events."""
        # Workbook events
        self.event_bus.subscribe(WorkbookStarted, self._on_workbook_started)
        self.event_bus.subscribe(WorkbookCompleted, self._on_workbook_completed)
        self.event_bus.subscribe(WorkbookCancelled, self._on_workbook_cancelled)
        self.event_bus.subscribe(WorkbookPaused, self._on_workbook_paused)
        self.event_bus.subscribe(WorkbookResumed, self._on_workbook_resumed)

        # Job events
        self.event_bus.subscribe(JobStarted, self._on_job_started)
        self.event_bus.subscribe(JobFailed, self._on_job_failed)
        self.event_bus.subscribe(JobPaused, self._on_job_paused)
        self.event_bus.subscribe(JobResumed, self._on_job_resumed)

        # Step events
        self.event_bus.subscribe(StepStarted, self._on_step_started)
        self.event_bus.subscribe(StepCompleted, self._on_step_completed)
        self.event_bus.subscribe(StepFailed, self._on_step_failed)

        logger.debug("Subscribed to all checkpoint events")

    def _on_workbook_started(self, event: BaseEvent) -> None:
        """Handle WorkbookStarted event."""
        assert isinstance(event, WorkbookStarted)
        doc = {
            "workbook_id": event.workbook_id,
            "workbook_name": event.workbook_name,
            "status": "RUNNING",
            "config": event.config,
            "dry_run": event.dry_run,
            "timestamp": event.timestamp.isoformat(),
        }
        self._index_document(doc)

    def _on_workbook_completed(self, event: BaseEvent) -> None:
        """Handle WorkbookCompleted event."""
        assert isinstance(event, WorkbookCompleted)
        doc = {
            "workbook_id": event.workbook_id,
            "workbook_name": event.workbook_name,
            "status": "COMPLETED",
            "results": event.results,
            "timestamp": event.timestamp.isoformat(),
        }
        self._index_document(doc)

    def _on_workbook_cancelled(self, event: BaseEvent) -> None:
        """Handle WorkbookCancelled event."""
        assert isinstance(event, WorkbookCancelled)
        doc = {
            "workbook_id": event.workbook_id,
            "workbook_name": event.workbook_name,
            "status": "CANCELLED",
            "reason": event.reason,
            "timestamp": event.timestamp.isoformat(),
        }
        self._index_document(doc)

    def _on_workbook_paused(self, event: BaseEvent) -> None:
        """Handle WorkbookPaused event."""
        assert isinstance(event, WorkbookPaused)
        doc = {
            "workbook_id": event.workbook_id,
            "workbook_name": event.workbook_name,
            "status": "PAUSED",
            "timestamp": event.timestamp.isoformat(),
        }
        self._index_document(doc)

    def _on_workbook_resumed(self, event: BaseEvent) -> None:
        """Handle WorkbookResumed event."""
        assert isinstance(event, WorkbookResumed)
        doc = {
            "workbook_id": event.workbook_id,
            "workbook_name": event.workbook_name,
            "status": "RUNNING",
            "timestamp": event.timestamp.isoformat(),
        }
        self._index_document(doc)

    def _on_job_started(self, event: BaseEvent) -> None:
        """Handle JobStarted event."""
        assert isinstance(event, JobStarted)
        doc = {
            "job_id": event.job_id,
            "workbook_id": event.workbook_id,
            "index": event.index,
            "status": "RUNNING",
            "timestamp": event.timestamp.isoformat(),
        }
        self._index_document(doc)

    def _on_job_failed(self, event: BaseEvent) -> None:
        """Handle JobFailed event."""
        assert isinstance(event, JobFailed)
        doc = {
            "job_id": event.job_id,
            "workbook_id": event.workbook_id,
            "status": "FAILED",
            "error": event.error,
            "timestamp": event.timestamp.isoformat(),
        }
        self._index_document(doc)

    def _on_job_paused(self, event: BaseEvent) -> None:
        """Handle JobPaused event."""
        assert isinstance(event, JobPaused)
        doc = {
            "job_id": event.job_id,
            "workbook_id": event.workbook_id,
            "status": "PAUSED",
            "timestamp": event.timestamp.isoformat(),
        }
        self._index_document(doc)

    def _on_job_resumed(self, event: BaseEvent) -> None:
        """Handle JobResumed event."""
        assert isinstance(event, JobResumed)
        doc = {
            "job_id": event.job_id,
            "workbook_id": event.workbook_id,
            "status": "RUNNING",
            "timestamp": event.timestamp.isoformat(),
        }
        self._index_document(doc)

    def _on_step_started(self, event: BaseEvent) -> None:
        """Handle StepStarted event."""
        assert isinstance(event, StepStarted)
        doc = {
            "step_id": event.step_id,
            "job_id": event.job_id,
            "step_name": event.step_name,
            "status": "RUNNING",
            "timestamp": event.timestamp.isoformat(),
        }
        self._index_document(doc)

    def _on_step_completed(self, event: BaseEvent) -> None:
        """Handle StepCompleted event."""
        assert isinstance(event, StepCompleted)
        doc = {
            "step_id": event.step_id,
            "job_id": event.job_id,
            "status": "COMPLETED",
            "timestamp": event.timestamp.isoformat(),
        }
        self._index_document(doc)

    def _on_step_failed(self, event: BaseEvent) -> None:
        """Handle StepFailed event."""
        assert isinstance(event, StepFailed)
        doc = {
            "step_id": event.step_id,
            "job_id": event.job_id,
            "status": "FAILED",
            "error": event.error,
            "timestamp": event.timestamp.isoformat(),
        }
        self._index_document(doc)

    def _ensure_index(self) -> None:
        """Create the tracking index with date mappings, or try to add them.

        Existing text/keyword ``timestamp`` mappings cannot be changed; that
        case is logged and indexing continues (Python re-sort still works).

        Single-threaded by contract (EventBus handlers share one worker).
        """
        # ponytail: global lock if EventBus goes multi-threaded
        if self._index_ready:
            return
        exists = self.client.indices.exists(index=self.tracking_index)
        if not exists:
            self.client.indices.create(
                index=self.tracking_index,
                mappings=TRACKING_DATE_MAPPING,
            )
        else:
            try:
                self.client.indices.put_mapping(
                    index=self.tracking_index,
                    properties=TRACKING_DATE_MAPPING["properties"],
                )
            except Exception as exc:
                logger.debug(
                    "Could not put date mapping on %s: %s",
                    self.tracking_index,
                    exc,
                )
        self._index_ready = True

    def _index_document(self, doc: dict[str, Any]) -> None:
        """Index a document to Elasticsearch.

        Args:
            doc: Document to index.

        Raises:
            Exception: If indexing fails.
        """
        if "timestamp" in doc and "@timestamp" not in doc:
            doc["@timestamp"] = doc["timestamp"]
        self._ensure_index()
        try:
            self.client.index(
                index=self.tracking_index,
                document=doc,
            )
            logger.debug(
                "Indexed document: %s",
                doc.get("workbook_id", doc.get("job_id", doc.get("step_id"))),
            )
        except Exception as exc:
            logger.error("Failed to index document: %s", exc)
            raise

    def get_workbook_history(self, workbook_id: str) -> list[dict[str, Any]]:
        """Get workbook history from Elasticsearch.

        Args:
            workbook_id: Workbook ID to query.

        Returns:
            List of history documents.
        """
        query = {
            "query": {
                "term": {
                    "workbook_id": workbook_id,
                }
            },
            "sort": [{"timestamp": {"order": "asc"}}],
        }

        try:
            response = self.client.search(
                index=self.tracking_index,
                body=query,
            )
            hits = response.get("hits", {}).get("hits", [])
            return [hit["_source"] for hit in hits]
        except Exception as exc:
            logger.error("Failed to get workbook history: %s", exc)
            return []

    def get_job_history(self, job_id: str) -> list[dict[str, Any]]:
        """Get job history from Elasticsearch.

        Args:
            job_id: Job ID to query.

        Returns:
            List of history documents.
        """
        query = {
            "query": {
                "term": {
                    "job_id": job_id,
                }
            },
            "sort": [{"timestamp": {"order": "asc"}}],
        }

        try:
            response = self.client.search(
                index=self.tracking_index,
                body=query,
            )
            hits = response.get("hits", {}).get("hits", [])
            return [hit["_source"] for hit in hits]
        except Exception as exc:
            logger.error("Failed to get job history: %s", exc)
            return []

    def get_step_status(self, step_id: str) -> dict[str, Any] | None:
        """Get step status from Elasticsearch.

        Args:
            step_id: Step ID to query.

        Returns:
            Step document or None if not found.
        """
        query = {
            "query": {
                "term": {
                    "step_id": step_id,
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}],
            "size": 1,
        }

        try:
            response = self.client.search(
                index=self.tracking_index,
                body=query,
            )
            hits = response.get("hits", {}).get("hits", [])
            if hits:
                return hits[0]["_source"]
            return None
        except Exception as exc:
            logger.error("Failed to get step status: %s", exc)
            return None
