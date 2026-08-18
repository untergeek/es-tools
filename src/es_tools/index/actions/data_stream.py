"""Delete and rollover data streams. Names are stream names (expand="none")."""

from __future__ import annotations

from typing import Any

from elasticsearch9 import NotFoundError

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end
from es_tools.wait.utils import response_dict


def _stream_present(client: Any, name: str) -> bool:
    try:
        body = response_dict(client.indices.get_data_stream(name=name))
    except NotFoundError:
        return False
    return bool(body.get("data_streams"))


class DeleteDataStreams:
    """Delete data streams and their backing indices.

    Example:
        >>> ActionRun(client, bus, "es-checkpoint").run(
        ...     DeleteDataStreams(), ["logs-nginx"]
        ... )
    """

    name = "delete_data_streams"
    mode: Mode = "chunked"
    wait_type: str | None = None

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Delete ``names``, retrying leftovers up to three times.

        Args:
            client: Elasticsearch client.
            names: One URI chunk of data-stream names.
            **opts: Unused.

        Returns:
            Failed ExecuteResult if any stream remains after three tries.
        """
        del opts
        remaining = list(names)
        for _ in range(3):
            if not remaining:
                break
            try:
                client.indices.delete_data_stream(name=",".join(remaining))
            except NotFoundError:
                pass
            remaining = [n for n in remaining if _stream_present(client, n)]
        if remaining:
            return ExecuteResult(
                ok=False,
                names=names,
                error=f"data streams still present after 3 deletes: {remaining}",
            )
        return ExecuteResult(ok=True, names=names)


class RolloverDataStreams:
    """Rollover each data stream if ``conditions`` are met.

    Data streams do not support ``new_index``. ``wait_for_active_shards``
    is passed to ES; this action does not use an ActionRun waiter.

    Args:
        conditions: Rollover conditions (``max_age``, ``max_docs``, …).
            An empty dict means unconditional rollover.
        wait_for_active_shards: ES ``wait_for_active_shards`` (default 1).

    Example:
        >>> ActionRun(client, bus, "es-checkpoint").run(
        ...     RolloverDataStreams({"max_age": "7d"}), ["logs-nginx"]
        ... )
    """

    name = "rollover_data_streams"
    mode: Mode = "per_item"
    wait_type: str | None = None

    def __init__(
        self,
        conditions: dict[str, Any],
        *,
        wait_for_active_shards: int = 1,
    ) -> None:
        if wait_for_active_shards < 1:
            raise ValueError("wait_for_active_shards must be >= 1")
        self.conditions = conditions
        self.wait_for_active_shards = wait_for_active_shards

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Rollover ``names[0]``.

        Args:
            client: Elasticsearch client.
            names: One-item unit (the data-stream name).
            **opts: Unused.

        Returns:
            ExecuteResult with the raw rollover response.
        """
        del opts
        kwargs: dict[str, Any] = {
            "alias": names[0],
            "wait_for_active_shards": self.wait_for_active_shards,
        }
        if self.conditions:
            kwargs["conditions"] = self.conditions
        raw = client.indices.rollover(**kwargs)
        return ExecuteResult(ok=True, names=names, raw=raw)
