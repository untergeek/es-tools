"""Unit tests for es_tools.wait module."""

from unittest.mock import Mock

import pytest

from es_tools.wait import Exists, Health, Task


class TestExists:
    """Test Exists waiter."""

    def test_exists_initialization(self):
        """Test creating an Exists waiter."""
        client = Mock()
        waiter = Exists(client, index="test_index")
        assert waiter is not None
        assert waiter.client == client

    def test_exists_wait(self):
        """Test waiting for index to exist."""
        client = Mock()
        client.indices.exists.return_value = True
        waiter = Exists(client, index="test_index")
        result = waiter.wait()
        assert result is True

    def test_exists_exception_counts_once(self):
        """A single polling failure increments the counter once."""
        client = Mock()
        client.indices.exists.side_effect = RuntimeError("down")
        waiter = Exists(client, index="test_index")
        assert waiter.check() is False
        assert waiter.exceptions_raised == 1
        assert len(waiter._exceptions) == 1


class TestHealth:
    """Test Health waiter."""

    def test_health_initialization(self):
        """Test creating a Health waiter."""
        client = Mock()
        waiter = Health(client)
        assert waiter is not None
        assert waiter.client == client

    def test_health_wait(self):
        """Test waiting for cluster health."""
        client = Mock()
        client.cluster.health.return_value = {"status": "green"}
        waiter = Health(client)
        result = waiter.wait()
        assert result is True

    def test_health_exception_counts_once(self):
        """A single health polling failure increments the counter once."""
        client = Mock()
        client.cluster.health.side_effect = RuntimeError("down")
        waiter = Health(client)
        assert waiter.check() is False
        assert waiter.exceptions_raised == 1
        assert len(waiter._exceptions) == 1


class TestTask:
    """Test Task waiter."""

    def test_task_initialization(self):
        """Test creating a Task waiter."""
        client = Mock()
        waiter = Task(client, task_id="test_task")
        assert waiter is not None
        assert waiter.task_id == "test_task"

    def test_task_empty_id_raises(self):
        """Empty task_id is rejected."""
        with pytest.raises(ValueError, match="task_id"):
            Task(Mock(), task_id="")

    def test_task_wait(self):
        """Test waiting for task to complete."""
        client = Mock()
        client.tasks.get.return_value = {
            "completed": True,
            "task": {
                "action": "indices:data/write/reindex",
                "running_time_in_nanos": 1000000000,
                "description": "test task",
                "start_time_in_millis": 1000,
            },
            "response": {"failures": []},
        }
        waiter = Task(client, task_id="test_task", timeout=5.0)
        result = waiter.wait()
        assert result is True

    def test_task_wait_raises_on_reindex_failures(self):
        """Top-level response.failures fail the waiter."""
        client = Mock()
        client.tasks.get.return_value = {
            "completed": True,
            "task": {
                "action": "indices:data/write/reindex",
                "running_time_in_nanos": 1000000000,
                "description": "test task",
                "start_time_in_millis": 1000,
            },
            "response": {"failures": [{"index": "dest", "cause": {"type": "x"}}]},
        }
        waiter = Task(client, task_id="test_task", timeout=5.0)
        with pytest.raises(ValueError, match="Failures"):
            waiter.check()

    def test_task_wait_raises_on_update_by_query_failures(self):
        """update_by_query response.failures must fail the waiter, not COMPLETED."""
        client = Mock()
        client.tasks.get.return_value = {
            "completed": True,
            "task": {
                "action": "indices:data/write/update/byquery",
                "running_time_in_nanos": 1000000000,
                "description": "update_by_query",
                "start_time_in_millis": 1000,
            },
            "response": {"failures": [{"index": "logs-1", "cause": {"type": "script_exception"}}]},
        }
        waiter = Task(client, action="update_by_query", task_id="ubq:1", timeout=5.0)
        with pytest.raises(ValueError, match="Failures"):
            waiter.check()

    def test_task_exception_counts_once(self):
        """A single task polling failure increments the counter once."""
        client = Mock()
        client.tasks.get.side_effect = RuntimeError("down")
        waiter = Task(client, task_id="test_task", timeout=5.0)
        assert waiter.check() is False
        assert waiter.exceptions_raised == 1
        assert len(waiter._exceptions) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
