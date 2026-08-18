"""Health Waiter for es_tools.wait."""

import logging
import typing as t

from es_tools.debug import begin_end, debug

from ._base import Waiter
from .defaults import HEALTH
from .utils import prettystr

if t.TYPE_CHECKING:
    from elasticsearch9 import Elasticsearch

logger = logging.getLogger(__name__)


class Health(Waiter):
    """Wait for Elasticsearch cluster health to reach a desired state.

    Polls the cluster health API to check if the cluster is in the desired state.

    Args:
        client (Elasticsearch): Elasticsearch client.
        check_type (str): Type of health check ('status', 'relocating_shards', etc.)
            (default: 'status').
        check_value (str): Desired value for the check (default: 'green').
        pause (float): Seconds between checks (default: 1.0).
        timeout (float): Max wait time in seconds (default: 30.0).
        max_exceptions (int): Max allowed exceptions (default: 10).

    Attributes:
        check_type (str): Type of health check.
        check_value (str): Desired value for the check.
        waitstr (str): Description of the wait operation.

    Example:
        >>> from elasticsearch9 import Elasticsearch
        >>> client = Elasticsearch()
        >>> waiter = Health(client, check_type="status", check_value="green")
        >>> waiter.wait()
    """

    def __init__(
        self,
        client: "Elasticsearch",
        check_type: str = "status",
        check_value: str = "green",
        pause: float = HEALTH["pause"],
        timeout: float = HEALTH["timeout"],
        max_exceptions: int = HEALTH["max_exceptions"],
    ) -> None:
        super().__init__(
            client=client, pause=pause, timeout=timeout, max_exceptions=max_exceptions
        )
        debug.lv2("Initializing Health object...")
        self.check_type = check_type
        self.check_value = check_value
        self.waitstr = f"for cluster health {self.check_type} to be {self.check_value}"
        self.announce()
        debug.lv3("Health object initialized")

    def __repr__(self) -> str:
        """Return a string representation of the Health instance."""
        return (
            f"Health(check_type={self.check_type!r}, check_value={self.check_value!r}, "
            f"waitstr={self.waitstr!r}, pause={self.pause})"
        )

    @begin_end()
    def check(self) -> bool:
        """Check if the cluster health matches the desired state.

        Returns:
            bool: True if health matches, False otherwise.
        """
        self.too_many_exceptions()
        try:
            debug.lv4("TRY: Getting cluster health")
            health = self.client.cluster.health()
            actual_value = health.get(self.check_type, "")
            debug.lv5(f"Cluster health: {self.check_type}={actual_value}")
            if actual_value == self.check_value:
                return True
            logger.info(
                f"Cluster {self.check_type} is '{actual_value}', "
                f"waiting for '{self.check_value}'"
            )
            return False
        except Exception as err:
            self.add_exception(err)
            logger.error("Error getting cluster health: %s", prettystr(err))
            return False
