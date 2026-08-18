"""Force-merge indices one at a time."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end


class ForceMerge:
    """Force-merge each index as its own Step.

    Args:
        max_num_segments: Target segments per shard. Must be >= 1.

    Example:
        >>> ActionRun(client, bus, "es-checkpoint").run(
        ...     ForceMerge(1), ["idx-1", "idx-2"], delay=0
        ... )
    """

    name = "forcemerge"
    mode: Mode = "per_item"
    wait_type: str | None = None

    def __init__(self, max_num_segments: int) -> None:
        if not isinstance(max_num_segments, int) or max_num_segments < 1:
            raise ValueError("max_num_segments must be an integer >= 1")
        self.max_num_segments = max_num_segments

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Force-merge a single index (``names[0]``).

        Args:
            client: Elasticsearch client.
            names: One-element list with the index name.
            **opts: Unused.

        Returns:
            ExecuteResult for that index.
        """
        client.indices.forcemerge(
            index=names[0],
            max_num_segments=self.max_num_segments,
        )
        return ExecuteResult(ok=True, names=names)
