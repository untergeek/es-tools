"""Clone source ILM, apply to mounted index, confirm target phase."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ActionRun
from es_tools.checkpoint.event_bus import EventBus
from es_tools.checkpoint.workbook import Workbook
from es_tools.index.actions.apply_ilm import ApplyIlmPolicy
from es_tools.index.actions.confirm_ilm import ConfirmIlmPhase
from es_tools.index.ilm import clone_ilm_policy


class RedactIlm:
    """The ILM half of pii-tool redaction (not restore/redact/mount)."""

    def __init__(
        self,
        client: Any,
        event_bus: EventBus,
        tracking_index: str,
        *,
        dry_run: bool = False,
    ) -> None:
        self.client = client
        self.event_bus = event_bus
        self.tracking_index = tracking_index
        self.dry_run = dry_run

    def run(self, source: str, mounted: str) -> Workbook | None:
        """Clone ``source`` policy, apply + confirm on ``mounted``.

        Returns:
            The confirm Workbook, or ``None`` if ``source`` is unmanaged.
        """
        cloned = clone_ilm_policy(self.client, source, dry_run=self.dry_run)
        if cloned is None:
            return None
        runner = ActionRun(
            self.client,
            self.event_bus,
            self.tracking_index,
            dry_run=self.dry_run,
        )
        runner.run(ApplyIlmPolicy(cloned.lifecycle), [mounted])
        return runner.run(ConfirmIlmPhase(cloned.phase), [mounted])
