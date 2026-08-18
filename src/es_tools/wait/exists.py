"""Exists Waiter for es_tools.wait."""

import logging
import typing as t

from es_tools.debug import begin_end, debug

from ._base import Waiter
from .defaults import EXISTS
from .utils import prettystr

if t.TYPE_CHECKING:
    from elasticsearch9 import Elasticsearch

logger = logging.getLogger(__name__)


class Exists(Waiter):
    """Wait for an Elasticsearch index to exist.

    Polls the cluster to check if an index exists.

    Args:
        client (Elasticsearch): Elasticsearch client.
        index (str): Index name to wait for.
        pause (float): Seconds between checks (default: 0.5).
        timeout (float): Max wait time in seconds (default: 30.0).
        max_exceptions (int): Max allowed exceptions (default: 10).

    Attributes:
        index (str): Index name to wait for.
        waitstr (str): Description of the wait operation.

    Example:
        >>> from elasticsearch9 import Elasticsearch
        >>> client = Elasticsearch()
        >>> waiter = Exists(client, index="my_index")
        >>> waiter.wait()
    """

    def __init__(
        self,
        client: "Elasticsearch",
        index: str,
        pause: float = EXISTS["pause"],
        timeout: float = EXISTS["timeout"],
        max_exceptions: int = EXISTS["max_exceptions"],
    ) -> None:
        super().__init__(
            client=client, pause=pause, timeout=timeout, max_exceptions=max_exceptions
        )
        debug.lv2("Initializing Exists object...")
        self.index = index
        self.waitstr = f"for index '{self.index}' to exist"
        self.announce()
        debug.lv3("Exists object initialized")

    def __repr__(self) -> str:
        """Return a string representation of the Exists instance."""
        return f"Exists(index={self.index!r}, waitstr={self.waitstr!r}, pause={self.pause})"

    @begin_end()
    def check(self) -> bool:
        """Check if the index exists.

        Returns:
            bool: True if index exists, False otherwise.
        """
        self.too_many_exceptions()
        try:
            debug.lv4("TRY: Checking if index exists")
            response = self.client.indices.exists(index=self.index)
            debug.lv5(f"Index exists response: {response}")
            return bool(response)
        except Exception as err:
            self.add_exception(err)
            logger.error("Error checking index existence: %s", prettystr(err))
            return False
