"""Create indices, one name per Step."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end

_ALREADY_EXISTS = {
    "resource_already_exists_exception",
    "index_already_exists_exception",
}


def _is_already_exists(exc: BaseException) -> bool:
    """Return True if ``exc`` is an ES already-exists error."""
    return getattr(exc, "error", None) in _ALREADY_EXISTS


class CreateIndices:
    """Create each name with optional settings, mappings, and aliases.

    Args:
        settings: Index settings body.
        mappings: Index mappings body.
        aliases: Aliases to attach at create time.
        ignore_existing: If True, treat already-exists as success.

    Example:
        >>> ActionRun(client, bus, "es-checkpoint").run(
        ...     CreateIndices(settings={"number_of_shards": 1}), ["logs-000001"]
        ... )
    """

    name = "create_index"
    mode: Mode = "per_item"
    wait_type: str | None = None

    def __init__(
        self,
        *,
        settings: dict[str, Any] | None = None,
        mappings: dict[str, Any] | None = None,
        aliases: dict[str, Any] | None = None,
        ignore_existing: bool = False,
    ) -> None:
        self.settings = settings
        self.mappings = mappings
        self.aliases = aliases
        self.ignore_existing = ignore_existing

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Create ``names[0]``.

        Args:
            client: Elasticsearch client.
            names: One-item unit from ActionRun.
            **opts: Unused.

        Returns:
            ExecuteResult for that index.
        """
        del opts
        kwargs: dict[str, Any] = {"index": names[0]}
        if self.settings is not None:
            kwargs["settings"] = self.settings
        if self.mappings is not None:
            kwargs["mappings"] = self.mappings
        if self.aliases is not None:
            kwargs["aliases"] = self.aliases
        try:
            client.indices.create(**kwargs)
        except Exception as exc:
            if self.ignore_existing and _is_already_exists(exc):
                return ExecuteResult(ok=True, names=names)
            raise
        return ExecuteResult(ok=True, names=names)
