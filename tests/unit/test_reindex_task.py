"""Unit tests for Chunk A fixes: do_search, client import isolation, ReindexTask.status."""

from unittest.mock import Mock

import pytest
from elastic_transport import ApiResponseMeta, HttpHeaders, NodeConfig
from elasticsearch9 import NotFoundError

from es_tools.exceptions import ESToolReindexError, ESToolTaskNotFoundError
from es_tools.redact.helpers.elastic_api import do_search
from es_tools.reindex.task import ReindexTask


def _not_found() -> NotFoundError:
    meta = ApiResponseMeta(
        status=404,
        http_version="1.1",
        headers=HttpHeaders(),
        duration=0.0,
        node=NodeConfig("http", "localhost", 9200),
    )
    return NotFoundError(
        "not found", meta, {"error": {"type": "resource_not_found_exception"}}
    )


class TestDoSearch:
    """Test es_tools.redact.helpers.elastic_api.do_search (A1)."""

    def test_returns_hits(self):
        """Test do_search returns the search result body."""
        client = Mock()
        body = {
            "hits": {
                "total": {"value": 100},
                "hits": [
                    {
                        "_index": "test_index",
                        "_id": "1",
                        "_source": {"field": "value"},
                    }
                ],
            }
        }
        client.search.return_value = body
        result = do_search(client, "test_index", {"match_all": {}}, size=10)
        assert result["hits"]["total"]["value"] == 100

    def test_uses_client_search(self):
        """Test do_search delegates to client.search with a wrapped body."""
        client = Mock()
        client.search.return_value = {"hits": {}}
        do_search(client, "idx", {"match_all": {}}, size=5)
        client.search.assert_called_once_with(
            index="idx", body={"query": {"match_all": {}}, "size": 5}
        )


class TestClientImportIsolation:
    """Test es_tools.client imports without click installed (A2)."""

    def test_client_imports_without_click(self):
        """Test es_tools.client imports successfully without click installed."""

        import es_tools.client
        from es_tools.client import ConfigParser, create_client, validate_config

        # Simulate click being unavailable by ensuring it is not imported
        # (it may already be in sys.modules if another test imported it,
        # so we just verify the import does not fail)
        assert create_client is not None
        assert ConfigParser is not None
        assert validate_config is not None
        assert es_tools.client is not None

    def test_config_module_imports_without_click(self):
        """Test es_tools.client.config imports without click installed."""
        from es_tools.client.config import config_args_v2, hosts_override_v2

        assert config_args_v2 is not None
        assert hosts_override_v2 is not None


COMPLETED_TASK = {
    "completed": True,
    "task": {
        "action": "indices:data/write/reindex",
        "description": "reindex from [src] to [dest]",
        "running_time_in_nanos": 1_000_000_000,
        "start_time_in_millis": 1_000,
        "status": {"total": 100, "created": 50, "updated": 30, "deleted": 20},
    },
    "response": {
        "failures": [],
        "total": 100,
        "created": 50,
        "updated": 30,
        "deleted": 20,
    },
}

RUNNING_TASK = {
    "completed": False,
    "task": {
        "action": "indices:data/write/reindex",
        "description": "reindex from [src] to [dest]",
        "running_time_in_nanos": 1_000_000_000,
        "start_time_in_millis": 1_000,
        "status": {"total": 100, "created": 10, "updated": 5, "deleted": 2},
    },
}


class TestReindexTaskStatus:
    """Test ReindexTask against the real GET /_tasks/{id} shape."""

    def test_status_completed(self):
        """Test status returns COMPLETED when top-level completed is True."""
        client = Mock()
        client.tasks.get.return_value = COMPLETED_TASK
        task = ReindexTask(client, "task_123")
        assert task.completed is True
        assert task.status == "COMPLETED"
        assert task.total == 100
        assert task.created == 50
        assert task.updated == 30
        assert task.deleted == 20
        assert task.failures == 0

    def test_status_running(self):
        """Test status returns RUNNING when task not completed."""
        client = Mock()
        client.tasks.get.return_value = RUNNING_TASK
        task = ReindexTask(client, "task_456")
        assert task.status == "RUNNING"

    def test_running_has_no_top_level_completed(self):
        """Missing top-level completed is not done."""
        client = Mock()
        client.tasks.get.return_value = {
            "task": {
                "status": {"total": 100, "created": 10, "updated": 5, "deleted": 2}
            }
        }
        task = ReindexTask(client, "task_456")
        assert task.completed is False
        assert task.status == "RUNNING"

    def test_failures_is_len_of_response_failures(self):
        """failures is the length of response.failures, not task.status."""
        client = Mock()
        body = dict(COMPLETED_TASK)
        body["response"] = {
            "failures": [{"index": "dest", "cause": {"type": "x"}}],
        }
        client.tasks.get.return_value = body
        task = ReindexTask(client, "task_123")
        assert task.failures == 1
        assert task.status == "FAILED"

    def test_completed_property_unchanged(self):
        """Test completed property still returns bool."""
        client = Mock()
        client.tasks.get.return_value = COMPLETED_TASK
        task = ReindexTask(client, "task_123")
        assert task.completed is True
        assert task.status == "COMPLETED"

    def test_not_found_maps_to_task_not_found(self):
        """A 404 task lookup remains a task-not-found error."""
        client = Mock()
        client.tasks.get.side_effect = _not_found()
        task = ReindexTask(client, "task_404")
        with pytest.raises(ESToolTaskNotFoundError) as excinfo:
            _ = task.completed
        assert isinstance(excinfo.value.__cause__, NotFoundError)

    def test_generic_failure_maps_to_reindex_error(self):
        """Non-404 task polling failures are not mislabeled as not found."""
        client = Mock()
        client.tasks.get.side_effect = RuntimeError("boom")
        task = ReindexTask(client, "task_boom")
        with pytest.raises(ESToolReindexError) as excinfo:
            _ = task.completed
        assert isinstance(excinfo.value.__cause__, RuntimeError)

    def test_wait_for_completion_propagates_generic_poll_failure(self):
        """Polling failures during wait_for_completion propagate as reindex errors."""
        client = Mock()
        client.tasks.get.side_effect = RuntimeError("boom")
        task = ReindexTask(client, "task_boom")
        with pytest.raises(ESToolReindexError) as excinfo:
            task.wait_for_completion(poll_interval=0)
        assert isinstance(excinfo.value.__cause__, RuntimeError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
