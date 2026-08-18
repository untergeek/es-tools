"""Snapshot Waiter for es_tools.wait."""

import logging
import typing as t

from es_tools.debug import begin_end, debug
from es_tools.exceptions import ESToolWaitFatal

from ._base import Waiter
from .defaults import SNAPSHOT
from .utils import prettystr, response_dict

if t.TYPE_CHECKING:
    from elasticsearch9 import Elasticsearch

logger = logging.getLogger(__name__)


class Snapshot(Waiter):
    """Wait for a snapshot to complete.

    Polls the snapshots API to check if a snapshot has completed.

    Args:
        client (Elasticsearch): Elasticsearch client.
        repository (str): Snapshot repository name.
        snapshot (str): Snapshot name.
        pause (float): Seconds between checks (default: 5.0).
        timeout (float): Max wait time in seconds (default: 600.0).
        max_exceptions (int): Max allowed exceptions (default: 10).

    Attributes:
        repository (str): Snapshot repository name.
        snapshot (str): Snapshot name.
        waitstr (str): Description of the wait operation.

    Example:
        >>> from elasticsearch9 import Elasticsearch
        >>> client = Elasticsearch()
        >>> waiter = Snapshot(client, repository="my_repo", snapshot="snap_1")
        >>> waiter.wait()
    """

    def __init__(
        self,
        client: "Elasticsearch",
        repository: str,
        snapshot: str,
        pause: float = SNAPSHOT["pause"],
        timeout: float = SNAPSHOT["timeout"],
        max_exceptions: int = SNAPSHOT["max_exceptions"],
    ) -> None:
        super().__init__(
            client=client, pause=pause, timeout=timeout, max_exceptions=max_exceptions
        )
        debug.lv2("Initializing Snapshot object...")
        self.repository = repository
        self.snapshot = snapshot
        self.waitstr = f"for snapshot '{self.snapshot}' in repository '{self.repository}' to complete"
        self.announce()
        debug.lv3("Snapshot object initialized")

    def __repr__(self) -> str:
        """Return a string representation of the Snapshot instance."""
        return (
            f"Snapshot(repository={self.repository!r}, snapshot={self.snapshot!r}, "
            f"waitstr={self.waitstr!r}, pause={self.pause})"
        )

    @begin_end()
    def check(self) -> bool:
        """Check if the snapshot is complete.

        Returns:
            bool: True if snapshot is complete, False otherwise.
        """
        self.too_many_exceptions()
        try:
            debug.lv4("TRY: Getting snapshot status")
            raw = response_dict(
                self.client.snapshot.get(
                    repository=self.repository, snapshot=self.snapshot
                )
            )
            wanted = None
            for snap in raw.get("snapshots") or []:
                if snap.get("snapshot") == self.snapshot:
                    wanted = snap
                    break
            if wanted is None:
                logger.warning("No snapshots named %s in response", self.snapshot)
                return False
            state = wanted.get("state", "")
            debug.lv5(f"Snapshot state: {state}")
            if state == "SUCCESS":
                return True
            if state in {"FAILED", "PARTIAL", "INCOMPATIBLE"}:
                raise ESToolWaitFatal(
                    f"snapshot {self.snapshot!r} in {self.repository!r} "
                    f"ended with state {state}"
                )
            logger.info("Snapshot state is %r, waiting for SUCCESS", state)
            return False
        except ESToolWaitFatal:
            raise
        except Exception as err:
            self.add_exception(err)
            logger.error("Error getting snapshot status: %s", prettystr(err))
            return False
