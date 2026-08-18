"""Base Waiter Class for es_tools.wait."""

import logging
import typing as t
from datetime import UTC, datetime
from time import sleep

from es_tools.debug import debug
from es_tools.exceptions import (
    ESToolWaitFatal,
    ESToolWaitTimeout,
)

from .defaults import BASE
from .utils import health_report

if t.TYPE_CHECKING:
    from elasticsearch9 import Elasticsearch

logger = logging.getLogger("es_tools.wait.Waiter")


class TimeTracker:
    """Track time for wait operations.

    Manages elapsed time and determines when to log progress based on frequency.

    Args:
        log_frequency: Seconds between log messages (default: 5).

    Attributes:
        log_frequency: Seconds between log messages.
        start_time: Start time in UTC.

    Example:
        >>> tracker = TimeTracker(log_frequency=10)
        >>> tracker.wait()  # doctest: +SKIP
    """

    def __init__(self, log_frequency: int = 5) -> None:
        debug.lv2("Initializing TimeTracker object...")
        self.log_frequency = log_frequency
        self.start_time = self.now
        debug.lv3("TimeTracker object initialized")

    @property
    def elapsed(self) -> float:
        """Return the elapsed time in seconds.

        Returns:
            float: Elapsed time since initialization in seconds.

        Example:
            >>> tracker = TimeTracker()
            >>> tracker.elapsed  # > 0.0
            12.5
        """
        return (self.now - self.start_time).total_seconds()

    @property
    def now(self) -> datetime:
        """Return the current time in UTC.

        Returns:
            datetime: Current time in UTC.

        Example:
            >>> tracker = TimeTracker()
            >>> tracker.now  # datetime
            datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        """
        return datetime.now(UTC)

    @property
    def should_log(self) -> bool:
        """Check if a log message should be generated.

        Returns True if elapsed time is non-zero and a multiple of log_frequency.

        Returns:
            bool: True if a log message should be generated, False otherwise.

        Example:
            >>> tracker = TimeTracker(log_frequency=5)
            >>> tracker.should_log  # > 0s elapsed
            True
        """
        if int(self.elapsed) == 0:
            return False
        return int(self.elapsed) % self.log_frequency == 0


class Waiter:
    """Base class for waiting on Elasticsearch operations.

    Manages polling, timeouts, and exceptions for tasks like index relocation or
    snapshot completion.

    Args:
        client: Elasticsearch client.
        pause: Seconds between checks (default: 9.0).
        timeout: Max wait time in seconds (default: 15.0, -1 for no timeout).
        max_exceptions: Max allowed exceptions (default: 10).

    Attributes:
        client: Elasticsearch client.
        pause: Seconds between checks.
        timeout: Max wait time in seconds.
        max_exceptions: Max allowed exceptions.
        exceptions_raised: Number of exceptions raised.
        do_health_report: If True, logs health report on failure.
        waitstr: Description of the wait operation.

    Example:
        >>> from es_tools.wait import Waiter
        >>> waiter = Waiter(client, waitstr="for a task to complete")
        >>> waiter.wait()  # doctest: +SKIP
    """

    def __init__(
        self,
        client: "Elasticsearch",
        pause: float = BASE["pause"],
        timeout: float = BASE["timeout"],
        max_exceptions: int = BASE["max_exceptions"],
    ) -> None:
        debug.lv2("Initializing Waiter object...")
        self.client = client
        self.pause = pause
        self.timeout = timeout
        self.max_exceptions = max_exceptions
        self._exceptions: list[Exception] = []
        self.exceptions_raised = 0
        self.waitstr = "for Waiter class to initialize"
        self.do_health_report = False
        debug.lv3("Waiter object initialized")

    @property
    def exception_count_msg(self) -> str:
        """Return a message showing the number of exceptions raised.

        Returns:
            str: A formatted message showing exceptions raised vs max.

        Example:
            >>> waiter = Waiter()
            >>> waiter.exceptions_raised = 3
            >>> waiter.exception_count_msg
            '3 of 10 exceptions raised'
        """
        return f"{self.exceptions_raised} of {self.max_exceptions} exceptions raised"

    def too_many_exceptions(self) -> None:
        """Check if too many exceptions have been raised.

        Raises:
            ESToolWaitFatal: If too many exceptions are raised.

        Example:
            >>> waiter = Waiter(max_exceptions=2)
            >>> waiter.exceptions_raised = 2
            >>> waiter.too_many_exceptions()  # Raises ESToolWaitFatal
        """
        if self.exceptions_raised >= self.max_exceptions:
            msg = f"{self.exception_count_msg} - too many exceptions"
            logger.error(msg)
            if self.do_health_report:
                health_report(self.client)
            raise ESToolWaitFatal(msg)

    def add_exception(self, exception: Exception) -> None:
        """Add an exception to the list of exceptions.

        Args:
            exception: Exception to add.

        Example:
            >>> waiter = Waiter()
            >>> waiter.add_exception(ValueError("test"))
        """
        self._exceptions.append(exception)
        self.exceptions_raised += 1

    def _ensure_not_none(self, name: str) -> None:
        """Ensure a value is not None.

        Args:
            name: Name of the value to check.

        Raises:
            ValueError: If value is None.

        Example:
            >>> waiter = Waiter()
            >>> waiter._ensure_not_none("task_id")
        """
        value = getattr(self, name, None)
        if value is None or value == "":
            raise ValueError(f"{name} cannot be None")

    def announce(self) -> None:
        """Announce the wait operation.

        Example:
            >>> waiter = Waiter(waitstr="for a task to complete")
            >>> waiter.announce()  # Logs info message
        """
        logger.info(f"Waiting {self.waitstr}")

    def wait(self) -> bool:
        """Wait for the operation to complete.

        Returns:
            bool: True if operation completed successfully.

        Raises:
            ESToolWaitTimeout: If timeout is reached.
            ESToolWaitFatal: If too many exceptions are raised.

        Example:
            >>> waiter = Waiter(waitstr="for a task to complete")
            >>> waiter.wait()  # doctest: +SKIP
            True
        """
        time_tracker = TimeTracker()
        while True:
            if time_tracker.should_log:
                logger.info(
                    f"Waiting {self.waitstr} - {time_tracker.elapsed:.1f} seconds"
                )
            if self.check():
                return True
            sleep(self.pause)
            if self.timeout > 0 and time_tracker.elapsed >= self.timeout:
                msg = f"Timeout after {self.timeout} seconds waiting {self.waitstr}"
                logger.error(msg)
                raise ESToolWaitTimeout(msg)

    def check(self) -> bool:
        """Check if the operation is complete.

        Returns:
            bool: True if operation is complete, False otherwise.

        Example:
            >>> waiter = Waiter()
            >>> waiter.check()  # Returns False by default
            False
        """
        return False
