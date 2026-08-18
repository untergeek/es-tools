"""Close indices in URI-sized chunks."""

from __future__ import annotations

import logging
from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode
from es_tools.debug import begin_end

logger = logging.getLogger(__name__)


class CloseIndices:
    """Close a list of indices.

    ``skip_flush`` defaults to False (flush before close).
    ``delete_aliases`` defaults to False; when True, ``pre_step_name``
    returns ``delete-aliases-N`` so ``ActionRun`` emits that Step before
    each ``close-N`` Step.

    Example:
        >>> ActionRun(client, bus, "es-checkpoint").run(
        ...     CloseIndices(), ["a"], skip_flush=False, delete_aliases=False
        ... )
    """

    name = "close"
    mode: Mode = "chunked"
    wait_type: str | None = None

    def pre_step_name(self, index: int, **opts: Any) -> str | None:
        """Return the pre-step name, or None to skip alias deletion.

        Args:
            index: 1-based unit number.
            **opts: Must include ``delete_aliases`` to emit a Step.

        Returns:
            ``delete-aliases-{index}`` when aliases should be stripped.
        """
        if opts.get("delete_aliases"):
            return f"delete-aliases-{index}"
        return None

    def execute_step_name(self, index: int, **opts: Any) -> str:
        """Return the execute Step name for this chunk.

        Args:
            index: 1-based unit number.
            **opts: Unused.

        Returns:
            ``close-{index}``.
        """
        del opts
        return f"close-{index}"

    @begin_end()
    def pre_execute(
        self, client: Any, names: list[str], **opts: Any
    ) -> ExecuteResult | None:
        """Strip all aliases from ``names`` when ``delete_aliases`` is set.

        Args:
            client: Elasticsearch client.
            names: One URI chunk of index names.
            **opts: Must include ``delete_aliases`` to take effect.

        Returns:
            ExecuteResult, or None when aliases should not be deleted.
        """
        if not opts.get("delete_aliases", False):
            return None
        try:
            client.indices.delete_alias(index=",".join(names), name="*")
        except Exception:
            logger.warning(
                "delete_alias failed for %s; continuing to close",
                names,
                exc_info=True,
            )
        return ExecuteResult(ok=True, names=names)

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Flush (unless skipped) and close ``names``.

        Args:
            client: Elasticsearch client.
            names: One URI chunk of index names.
            **opts: ``skip_flush`` (default False).

        Returns:
            ExecuteResult for the chunk.
        """
        csv = ",".join(names)
        if not opts.get("skip_flush", False):
            client.indices.flush(index=csv, ignore_unavailable=True, force=True)
        client.indices.close(index=csv, ignore_unavailable=True)
        return ExecuteResult(ok=True, names=names)
