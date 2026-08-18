"""ILM Waiters for es_tools.wait."""

import logging
import typing as t

from es_tools.debug import begin_end, debug
from es_tools.exceptions import ESToolIlmWaitError

from ._base import Waiter
from .defaults import ILM
from .utils import prettystr, response_dict

if t.TYPE_CHECKING:
    from elasticsearch9 import Elasticsearch

logger = logging.getLogger(__name__)

PHASE_ORDER: tuple[str, ...] = ("new", "hot", "warm", "cold", "frozen", "delete")


def phase_reached(current: str, target: str) -> bool:
    """True if ``current`` is ``target`` or a later ILM phase."""
    if current not in PHASE_ORDER or target not in PHASE_ORDER:
        return False
    return PHASE_ORDER.index(current) >= PHASE_ORDER.index(target)


def explain_index(client: "Elasticsearch", index: str) -> dict[str, t.Any]:
    """Return the per-index ILM explain body.

    Args:
        client: Elasticsearch client.
        index: Index name.

    Returns:
        The ``indices[index]`` mapping from ``explain_lifecycle``.

    Raises:
        ESToolIlmWaitError: Index missing from the response or not managed.
    """
    raw = client.ilm.explain_lifecycle(index=index)
    body = response_dict(raw)
    info = (body.get("indices") or {}).get(index) or {}
    if not info:
        raise ESToolIlmWaitError(f"ILM explain has no entry for index {index!r}")
    if not info.get("managed"):
        raise ESToolIlmWaitError(f"index {index} is not managed by ILM")
    return info


class IlmPhase(Waiter):
    """Wait for an ILM phase to complete.

    Polls the ILM explain API to check if an index has completed a phase.

    Args:
        client (Elasticsearch): Elasticsearch client.
        index (str): Index name.
        phase (str): ILM phase to wait for (new/hot/warm/cold/frozen/delete).
        pause (float): Seconds between checks (default: 2.0).
        timeout (float): Max wait time in seconds (default: 60.0).
        max_exceptions (int): Max allowed exceptions (default: 10).

    Attributes:
        index (str): Index name.
        phase (str): ILM phase to wait for.
        waitstr (str): Description of the wait operation.

    Example:
        >>> from elasticsearch9 import Elasticsearch
        >>> client = Elasticsearch()
        >>> waiter = IlmPhase(client, index="my_index", phase="cold")
        >>> waiter.wait()
    """

    def __init__(
        self,
        client: "Elasticsearch",
        index: str,
        phase: str,
        pause: float = ILM["pause"],
        timeout: float = ILM["timeout"],
        max_exceptions: int = ILM["max_exceptions"],
    ) -> None:
        super().__init__(
            client=client, pause=pause, timeout=timeout, max_exceptions=max_exceptions
        )
        debug.lv2("Initializing IlmPhase object...")
        self.index = index
        self.phase = phase
        if phase not in PHASE_ORDER:
            raise ValueError(f"phase must be one of {PHASE_ORDER}, got {phase!r}")
        self.waitstr = (
            f"for ILM phase '{self.phase}' on index '{self.index}' to complete"
        )
        self.announce()
        debug.lv3("IlmPhase object initialized")

    def __repr__(self) -> str:
        """Return a string representation of the IlmPhase instance."""
        return (
            f"IlmPhase(index={self.index!r}, phase={self.phase!r}, "
            f"waitstr={self.waitstr!r}, pause={self.pause})"
        )

    @begin_end()
    def check(self) -> bool:
        """Check if the ILM phase is complete.

        Returns:
            bool: True if phase is complete, False otherwise.

        Raises:
            ESToolIlmWaitError: If the index is not managed by ILM.
        """
        self.too_many_exceptions()
        try:
            debug.lv4("TRY: Getting ILM explain")
            phase_status = explain_index(self.client, self.index).get("phase", "")
            debug.lv5(f"ILM phase status: {phase_status}")
            if phase_reached(str(phase_status), self.phase):
                return True
            logger.info(
                f"ILM phase status is '{phase_status}', waiting for '{self.phase}'"
            )
            return False
        except ESToolIlmWaitError:
            raise
        except Exception as err:
            self.add_exception(err)
            logger.error("Error getting ILM explain: %s", prettystr(err))
            return False


class IlmStep(Waiter):
    """Wait for an ILM step to complete.

    Polls the ILM explain API to check if an index has completed a step.

    Args:
        client (Elasticsearch): Elasticsearch client.
        index (str): Index name.
        step (str): ILM step to wait for (e.g., 'complete', 'migrate').
        pause (float): Seconds between checks (default: 2.0).
        timeout (float): Max wait time in seconds (default: 60.0).
        max_exceptions (int): Max allowed exceptions (default: 10).

    Attributes:
        index (str): Index name.
        step (str): ILM step to wait for.
        waitstr (str): Description of the wait operation.

    Example:
        >>> from elasticsearch9 import Elasticsearch
        >>> client = Elasticsearch()
        >>> waiter = IlmStep(client, index="my_index", step="complete")
        >>> waiter.wait()
    """

    def __init__(
        self,
        client: "Elasticsearch",
        index: str,
        step: str,
        pause: float = ILM["pause"],
        timeout: float = ILM["timeout"],
        max_exceptions: int = ILM["max_exceptions"],
    ) -> None:
        super().__init__(
            client=client, pause=pause, timeout=timeout, max_exceptions=max_exceptions
        )
        debug.lv2("Initializing IlmStep object...")
        self.index = index
        self.step = step
        self.waitstr = f"for ILM step '{self.step}' on index '{self.index}' to complete"
        self.announce()
        debug.lv3("IlmStep object initialized")

    def __repr__(self) -> str:
        """Return a string representation of the IlmStep instance."""
        return (
            f"IlmStep(index={self.index!r}, step={self.step!r}, "
            f"waitstr={self.waitstr!r}, pause={self.pause})"
        )

    @begin_end()
    def check(self) -> bool:
        """Check if the ILM step is complete.

        Returns:
            bool: True if step is complete, False otherwise.

        Raises:
            ESToolIlmWaitError: If the index is not managed by ILM.
        """
        self.too_many_exceptions()
        try:
            debug.lv4("TRY: Getting ILM explain")
            step_status = explain_index(self.client, self.index).get("step", "")
            debug.lv5(f"ILM step status: {step_status}")
            if step_status == self.step:
                return True
            logger.info(
                f"ILM step status is '{step_status}', waiting for '{self.step}'"
            )
            return False
        except ESToolIlmWaitError:
            raise
        except Exception as err:
            self.add_exception(err)
            logger.error("Error getting ILM explain: %s", prettystr(err))
            return False
