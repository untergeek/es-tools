"""Reindex each source index into a destination (async + task wait)."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end


class ReindexIndices:
    """Reindex each source name into ``dest``.

    Starts the ES reindex with ``wait_for_completion=False`` and returns
    the task id so ``ActionRun`` can wait via ``wait_type="task"``.

    Args:
        dest: Destination index name.
        body_extra: Extra ``client.reindex`` kwargs. Nested ``source`` /
            ``dest`` mappings are merged; ``index`` still comes from the
            unit name and ``dest``.

    Raises:
        ValueError: If ``dest`` is empty.

    Example:
        >>> ActionRun(client, bus, "es-checkpoint").run(
        ...     ReindexIndices("dest-idx"), ["src-1", "src-2"]
        ... )
    """

    name = "reindex"
    mode: Mode = "per_item"
    wait_type: str | None = "task"

    def __init__(
        self,
        dest: str,
        *,
        body_extra: dict[str, Any] | None = None,
    ) -> None:
        if not dest:
            raise ValueError("dest must be a non-empty string")
        self.dest = dest
        self.body_extra = dict(body_extra or {})

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Start an async reindex of ``names[0]`` into ``dest``.

        Args:
            client: Elasticsearch client.
            names: One-item unit (source index).
            **opts: Unused.

        Returns:
            ExecuteResult with ``task_id`` from the ES response.
        """
        del opts
        extra = dict(self.body_extra)
        source_extra = dict(extra.pop("source", {}) or {})
        dest_extra = dict(extra.pop("dest", {}) or {})
        source_extra["index"] = names[0]
        dest_extra["index"] = self.dest
        raw = client.reindex(
            source=source_extra,
            dest=dest_extra,
            wait_for_completion=False,
            **extra,
        )
        task_id = raw.get("task") if hasattr(raw, "get") else None
        return ExecuteResult(ok=True, names=names, raw=raw, task_id=task_id)
