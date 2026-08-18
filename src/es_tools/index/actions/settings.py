"""Put index settings in URI-sized chunks."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end


class PutIndexSettings:
    """Apply settings to a list of indices.

    Args:
        settings: Non-empty settings mapping for ``indices.put_settings``.

    Example:
        >>> PutIndexSettings({"index": {"refresh_interval": "1s"}})
    """

    name = "index_settings"
    mode: Mode = "chunked"
    wait_type: str | None = None

    def __init__(self, settings: dict[str, Any]) -> None:
        if not settings:
            raise ValueError("settings must be a non-empty dict")
        self.settings = settings

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Put settings on ``names``.

        Args:
            client: Elasticsearch client.
            names: One URI chunk of index names.
            **opts: Optional ``settings`` mapping overrides the constructor
                body for this unit.

        Returns:
            ExecuteResult for the chunk.
        """
        body = opts.get("settings", self.settings)
        client.indices.put_settings(index=",".join(names), settings=body)
        return ExecuteResult(ok=True, names=names)
