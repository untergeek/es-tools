"""Restore waiter: poll index recovery until snapshot restore shards are DONE."""

from __future__ import annotations

import logging
from typing import Any

from es_tools.debug import begin_end, debug
from es_tools.utils.chunk import chunk_names

from ._base import Waiter
from .defaults import RESTORE
from .utils import prettystr

logger = logging.getLogger(__name__)


def _as_mapping(raw: Any) -> dict[str, Any]:
    """Normalize an ES recovery response to a plain dict."""
    if raw is None:
        return {}
    if hasattr(raw, "body"):
        raw = raw.body
    if isinstance(raw, dict):
        return raw
    try:
        return dict(raw)
    except (TypeError, ValueError):
        return {}


def _shards_of(index_body: Any) -> list[dict[str, Any]]:
    """Return the shard list for one index entry."""
    if not isinstance(index_body, dict):
        return []
    shards = index_body.get("shards", [])
    if not isinstance(shards, list):
        return []
    return [s for s in shards if isinstance(s, dict)]


def _source_blob(shard: dict[str, Any]) -> dict[str, Any]:
    """Return the shard ``source`` mapping if present."""
    source = shard.get("source")
    return source if isinstance(source, dict) else {}


class Restore(Waiter):
    """Wait for a snapshot restore via the Recovery API.

    Discovers restored index names from cluster ``GET /_recovery`` (shards
    with ``type == SNAPSHOT``, optionally filtered by repository/snapshot),
    then polls those indices until every shard is ``DONE``.

    Args:
        client: Elasticsearch client.
        indices: Optional restrictor; intersection with discovered names.
        repository: Optional snapshot repository filter on shard source.
        snapshot: Optional snapshot name filter on shard source.
        pause: Seconds between checks (default: 5.0).
        timeout: Max wait time in seconds (default: 7200.0).
        max_exceptions: Max allowed exceptions (default: 10).

    Example:
        >>> waiter = Restore(client, repository="my_repo", snapshot="snap_1")
        >>> waiter.wait()
    """

    def __init__(
        self,
        client: Any,
        indices: list[str] | None = None,
        repository: str | None = None,
        snapshot: str | None = None,
        pause: float = RESTORE["pause"],
        timeout: float = RESTORE["timeout"],
        max_exceptions: int = RESTORE["max_exceptions"],
    ) -> None:
        if indices is not None and not isinstance(indices, (list, tuple)):
            raise TypeError(
                "indices must be a list of index names "
                "(task_id is not supported; restore waits on recovery)"
            )
        super().__init__(
            client=client, pause=pause, timeout=timeout, max_exceptions=max_exceptions
        )
        debug.lv2("Initializing Restore object...")
        self.restrictor = list(indices) if indices else None
        self.repository = repository
        self.snapshot = snapshot
        self._tracked: set[str] = set()
        self.waitstr = "for snapshot restore recoveries to complete"
        self.announce()
        debug.lv3("Restore object initialized")

    def __repr__(self) -> str:
        """Return a string representation of the Restore instance."""
        return (
            f"Restore(indices={self.restrictor!r}, repository={self.repository!r}, "
            f"snapshot={self.snapshot!r}, waitstr={self.waitstr!r}, pause={self.pause})"
        )

    def _shard_is_snapshot(self, shard: dict[str, Any]) -> bool:
        """Return True if this shard is a snapshot restore (optionally filtered)."""
        stype = str(shard.get("type") or "").upper()
        source = _source_blob(shard)
        is_snap = stype == "SNAPSHOT" or bool(
            source.get("snapshot") or source.get("repository")
        )
        if not is_snap:
            return False
        if self.repository and source.get("repository") not in (None, self.repository):
            return False
        if self.snapshot and source.get("snapshot") not in (None, self.snapshot):
            return False
        return True

    def _discover(self, recovery: dict[str, Any]) -> set[str]:
        """Return index names with at least one snapshot-restore shard."""
        found: set[str] = set()
        for name, body in recovery.items():
            if any(self._shard_is_snapshot(shard) for shard in _shards_of(body)):
                found.add(str(name))
        if self.restrictor is not None:
            allowed = set(self.restrictor)
            found &= allowed
        return found

    def _all_done(self, recovery: dict[str, Any], names: set[str]) -> bool:
        """Return True if every tracked index is present and restore shards are DONE."""
        for name in names:
            if name not in recovery:
                logger.info("Recovery response missing tracked index %s", name)
                return False
            shards = _shards_of(recovery[name])
            if not shards:
                logger.info("Index %s has no recovery shards yet", name)
                return False
            restore_shards = [
                shard for shard in shards if self._shard_is_snapshot(shard)
            ]
            if not restore_shards:
                logger.info("Index %s has no restore shards in targeted recovery", name)
                return False
            for shard in restore_shards:
                stage = str(shard.get("stage") or "").upper()
                if stage != "DONE":
                    logger.info("Index %s is still in stage %s", name, stage)
                    return False
        return True

    @begin_end()
    def check(self) -> bool:
        """Check whether discovered restore recoveries are complete.

        Returns:
            True if every tracked index has all matching restore shards in stage DONE.
        """
        self.too_many_exceptions()
        try:
            debug.lv4("TRY: Cluster recovery for restore discovery")
            cluster = _as_mapping(self.client.indices.recovery())
        except Exception as err:
            self.add_exception(err)
            logger.error("Error getting cluster recovery: %s", prettystr(err))
            return False

        if not cluster:
            logger.info("_recovery returned an empty response. Trying again.")
            return False

        self._tracked |= self._discover(cluster)
        if not self._tracked:
            logger.info("No SNAPSHOT recoveries discovered yet")
            return False

        targeted: dict[str, Any] = {}
        try:
            for chunk in chunk_names(sorted(self._tracked)):
                debug.lv4(f"TRY: Targeted recovery for {chunk}")
                piece = _as_mapping(self.client.indices.recovery(index=",".join(chunk)))
                if not piece:
                    logger.info("_recovery for %s was empty. Trying again.", chunk)
                    return False
                targeted.update(piece)
        except Exception as err:
            self.add_exception(err)
            logger.error("Error getting index recovery: %s", prettystr(err))
            return False

        return self._all_done(targeted, self._tracked)
