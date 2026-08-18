"""Tests for ShrinkIndices pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from es_tools.checkpoint.action_run import ActionRun, ExecuteResult, Mode, StepSpec
from es_tools.checkpoint.event_bus import EventBus
from es_tools.index.actions import ShrinkIndices


def test_shrink_rejects_empty_node() -> None:
    """shrink_node is required."""
    with pytest.raises(ValueError, match="shrink_node"):
        ShrinkIndices("")


def test_shrink_rejects_empty_affix() -> None:
    """Target name must differ from source."""
    with pytest.raises(ValueError, match="shrink_prefix"):
        ShrinkIndices("n1", shrink_prefix="", shrink_suffix="")


def test_shrink_pipeline_default_steps() -> None:
    """Default pipeline is route, wait, block, shrink, delete."""
    client = MagicMock()
    client.indices.exists.return_value = False
    mock_relocate = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("es_tools.wait.relocate.Relocate", mock_relocate)
        wb = ActionRun(client, EventBus(), "es-checkpoint").run(
            ShrinkIndices("es-data-1"), ["logs-1"]
        )
    assert [s.name for s in wb.jobs[0].steps] == [
        "route-1",
        "wait-relocate-1",
        "block-writes-1",
        "shrink-1",
        "delete-1",
    ]
    client.indices.put_settings.assert_any_call(
        index="logs-1",
        settings={"index.routing.allocation.require._name": "es-data-1"},
    )
    client.indices.put_settings.assert_any_call(
        index="logs-1", settings={"index.blocks.write": True}
    )
    client.indices.shrink.assert_called_once()
    shrink_kwargs = client.indices.shrink.call_args.kwargs
    assert shrink_kwargs["index"] == "logs-1"
    assert shrink_kwargs["target"] == "logs-1-shrink"
    assert shrink_kwargs["settings"]["index.number_of_shards"] == 1
    client.indices.delete.assert_called_once_with(index="logs-1")
    mock_relocate.assert_called_once()
    assert mock_relocate.call_args.kwargs["node"] == "es-data-1"
    mock_relocate.return_value.wait.assert_called_once()
    assert wb.status == "COMPLETED"


def test_shrink_copy_aliases_and_keep_source() -> None:
    """copy_aliases + delete_after=False emit aliases then unroute."""
    client = MagicMock()
    client.indices.exists.return_value = False
    client.indices.get_alias.return_value = {"logs-1": {"aliases": {"logs-write": {}}}}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("es_tools.wait.relocate.Relocate", MagicMock())
        wb = ActionRun(client, EventBus(), "es-checkpoint").run(
            ShrinkIndices(
                "es-data-1",
                copy_aliases=True,
                delete_after=False,
            ),
            ["logs-1"],
        )
    names = [s.name for s in wb.jobs[0].steps]
    assert names[-2:] == ["aliases-1", "unroute-1"]
    client.indices.update_aliases.assert_called_once()
    actions = client.indices.update_aliases.call_args.kwargs["actions"]
    assert {"remove": {"index": "logs-1", "alias": "logs-write"}} in actions
    assert {"add": {"index": "logs-1-shrink", "alias": "logs-write"}} in actions
    client.indices.delete.assert_not_called()
    client.indices.put_settings.assert_any_call(
        index="logs-1",
        settings={"index.routing.allocation.require._name": None},
    )
    assert wb.status == "COMPLETED"


def test_shrink_refuses_existing_target() -> None:
    """Pre-existing target is a failed result, not a delete."""
    client = MagicMock()
    client.indices.exists.return_value = True
    result = ShrinkIndices("n1")._shrink(client, "logs-1")
    assert result.ok is False
    assert "already exists" in (result.error or "")
    client.indices.shrink.assert_not_called()
    client.indices.delete.assert_not_called()


def test_shrink_deletes_target_only_if_created_this_call() -> None:
    """On shrink failure, delete the target only if we created it."""
    client = MagicMock()
    client.indices.exists.side_effect = [False, True]
    client.indices.shrink.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        ShrinkIndices("n1")._shrink(client, "logs-1")
    client.indices.delete.assert_called_once_with(index="logs-1-shrink")


def test_shrink_does_not_delete_if_target_absent_after_failure() -> None:
    """No delete when the target never appeared."""
    client = MagicMock()
    client.indices.exists.side_effect = [False, False]
    client.indices.shrink.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        ShrinkIndices("n1")._shrink(client, "logs-1")
    client.indices.delete.assert_not_called()


def test_shrink_dry_run_skips_es() -> None:
    """dry_run emits pipeline Steps and does not call ES."""
    client = MagicMock()
    mock_relocate = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("es_tools.wait.relocate.Relocate", mock_relocate)
        wb = ActionRun(client, EventBus(), "es-checkpoint", dry_run=True).run(
            ShrinkIndices("es-data-1"), ["logs-1"]
        )
    client.indices.shrink.assert_not_called()
    client.indices.put_settings.assert_not_called()
    mock_relocate.assert_not_called()
    assert [s.name for s in wb.jobs[0].steps] == [
        "route-1",
        "wait-relocate-1",
        "block-writes-1",
        "shrink-1",
        "delete-1",
    ]


class DummyPipe:
    """Pipeline dummy so execute is not used."""

    name = "pipe"
    mode: Mode = "per_item"
    wait_type: str | None = None

    def pipeline(self, index: int, names: list[str], **opts: object) -> list[StepSpec]:
        return [
            StepSpec(f"one-{index}", op="one"),
            StepSpec(f"two-{index}", op="two"),
        ]

    def run_step(
        self, spec: StepSpec, client: object, names: list[str], **opts: object
    ) -> ExecuteResult:
        return ExecuteResult(ok=True, names=names)

    def execute(
        self, client: object, names: list[str], **opts: object
    ) -> ExecuteResult:
        raise AssertionError("execute must not run when pipeline is set")


def test_action_run_uses_pipeline_not_execute() -> None:
    """pipeline replaces pre/execute/wait for that action."""
    wb = ActionRun(object(), EventBus(), "es-checkpoint").run(DummyPipe(), ["a"])
    assert [s.name for s in wb.jobs[0].steps] == ["one-1", "two-1"]
    assert wb.status == "COMPLETED"
