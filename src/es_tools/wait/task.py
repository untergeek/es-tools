"""Task Completion Waiter for es_tools.wait."""

import logging
import typing as t
import warnings
from time import localtime, strftime

from elasticsearch9.exceptions import GeneralAvailabilityWarning

from es_tools.debug import begin_end, debug

from ..utils.attrdict import AttrDict
from ._base import Waiter
from .defaults import TASK
from .utils import prettystr, response_dict

if t.TYPE_CHECKING:
    from elasticsearch9 import Elasticsearch

logger = logging.getLogger(__name__)


class Task(Waiter):
    """Wait for an Elasticsearch task to complete.

    Polls the tasks.get API to check if a task (e.g., reindex) is complete.

    Args:
        client (Elasticsearch): Elasticsearch client.
        pause (float): Seconds between checks (default: 9.0).
        timeout (float): Max wait time in seconds (default: 7200.0).
        max_exceptions (int): Max allowed exceptions (default: 10).
        action (Literal['forcemerge', 'reindex', 'update_by_query']): Task type
            (default: 'reindex').
        task_id (str): Task identifier (default: '').

    Attributes:
        action (Literal['forcemerge', 'reindex', 'update_by_query']): Task type.
        task_id (str): Task identifier.
        task_data (AttrDict): Task data from tasks.get API.
        task (AttrDict): Task details from task_data.
        failure_count (int): Number of task failures.
        waitstr (str): Description of the wait operation.

    Raises:
        ValueError: If `task_id` is empty or `action` is invalid.

    Example:
        >>> from elasticsearch9 import Elasticsearch
        >>> client = Elasticsearch()
        >>> task = Task(client, action="reindex", task_id="123")
        >>> task.wait()
    """

    def __init__(
        self,
        client: "Elasticsearch",
        pause: float = TASK["pause"],
        timeout: float = TASK["timeout"],
        max_exceptions: int = TASK["max_exceptions"],
        action: t.Literal["forcemerge", "reindex", "update_by_query"] = "reindex",
        task_id: str = "",
    ) -> None:
        super().__init__(
            client=client, pause=pause, timeout=timeout, max_exceptions=max_exceptions
        )
        debug.lv2("Initializing Task object...")
        self.action = action
        if action not in ["forcemerge", "reindex", "update_by_query"]:
            msg = "The action must be one of forcemerge, reindex, or update_by_query"
            logger.error(msg)
            raise ValueError(msg)
        self.task_id = task_id
        self._ensure_not_none("task_id")
        self.task_data: AttrDict | None = None
        self.task: AttrDict | None = None
        self.failure_count = 0
        self.waitstr = f'for the "{self.action}" task to complete'
        self.announce()
        debug.lv3("Task object initialized")

    def __repr__(self) -> str:
        """Return a string representation of the Task instance."""
        parts = [
            f"action={self.action!r}",
            f"task_id={self.task_id!r}",
            f"waitstr={self.waitstr!r}",
            f"pause={self.pause}",
        ]
        return f"{self.__class__.__name__}({', '.join(parts)})"

    @property
    @begin_end()
    def task_complete(self) -> bool:
        """Check if the task is complete.

        Returns True if the task is marked as completed, False otherwise.

        Returns:
            bool: True if task is complete, False otherwise.
        """
        if self.task is None or self.task_data is None:
            raise ValueError("task data has not been loaded")
        running_time = 0.000000001 * self.task.running_time_in_nanos
        debug.lv3(f"Running time: {running_time} seconds")
        if self.task_data.completed:
            completion_time = running_time * 1000
            completion_time += self.task["start_time_in_millis"]
            time_string = strftime(
                "%Y-%m-%dT%H:%M:%S", localtime(completion_time / 1000)
            )
            msg = (
                f'Task "{self.task.description}" with task_id '
                f'"{self.task_id}" completed at {time_string}'
            )
            debug.lv3(msg)
            retval = True
        else:
            _ = self.task_data.toDict()
            debug.lv5(f"Full Task Data: {prettystr(_)}")
            msg = (
                f'Task "{self.task.description}" with task_id '
                f'"{self.task_id}" has been running for {running_time} seconds'
            )
            debug.lv3(msg)
            retval = False
        debug.lv5(f"Return value = {retval}")
        return retval

    @begin_end()
    def check(self) -> bool:
        """Check if the task is complete.

        Calls tasks.get to update task_data and checks for completion.

        Returns:
            bool: True if task is complete, False otherwise.

        Raises:
            ValueError: If task information cannot be obtained.
        """
        self.too_many_exceptions()
        response = {}
        try:
            debug.lv4("TRY: Getting task information")
            warnings.filterwarnings("ignore", category=GeneralAvailabilityWarning)
            response = response_dict(self.client.tasks.get(task_id=self.task_id))
            debug.lv5(f"tasks.get response: {response}")
        except Exception as err:
            self.add_exception(err)
            msg = (
                f'Unable to obtain task information for task_id "{self.task_id}". '
                f"Response: {prettystr(response)} -- "
                f"Exception: {prettystr(err)}"
            )
            logger.error(msg)
            return False
        self.task_data = AttrDict(response)
        self.task = AttrDict(self.task_data.task)
        debug.lv4("TRY: Checking for reindex task")
        self.reindex_check()
        debug.lv5(f"Return value = {self.task_complete}")
        return self.task_complete

    @begin_end()
    def reindex_check(self) -> None:
        """Check for task response failures.

        Raises a ValueError if the completed task has ``response.failures``.
        Applies to reindex, update_by_query, and any other task that returns
        a failures list — not only reindex.

        Raises:
            ValueError: If the task response has failures.
        """
        if self.task is None or self.task_data is None:
            return
        debug.lv5(f"TASK_DATA: {prettystr(self.task_data.toDict())}")
        body = self.task_data.toDict()
        failures = (body.get("response") or {}).get("failures") or []
        if failures:
            msg = f"Failures found in the {self.action} response: {prettystr(failures)}"
            logger.error(msg)
            debug.lv3("Exiting method, raising ValueError")
            raise ValueError(msg)
