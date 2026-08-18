"""Real-cluster tests against ElasticsearchDocker."""

from __future__ import annotations

import time
from typing import Any

import pytest

from es_tools.checkpoint.action_run import ActionRun
from es_tools.checkpoint.event_bus import EventBus
from es_tools.index.actions import CloseIndices, ReindexIndices
from es_tools.redact.ilm import RedactIlm
from es_tools.wait.relocate import Relocate

pytestmark = pytest.mark.docker


def _create_index(
    client: Any, name: str, settings: dict[str, Any] | None = None
) -> str:
    """Create an index for a docker integration test."""
    body: dict[str, Any] = {}
    if settings:
        body["settings"] = settings
    client.indices.create(index=name, body=body)
    return name


def test_cluster_health_is_ready(es_client) -> None:
    """Single-node docker cluster reaches yellow or green."""
    status = es_client.cluster.health()["status"]
    assert status in {"green", "yellow"}


def test_action_run_closes_index(es_client) -> None:
    """ActionRun CloseIndices closes an index created for the test."""
    name = _create_index(es_client, "itest_closeme")
    try:
        wb = ActionRun(es_client, EventBus(), "es-checkpoint").run(
            CloseIndices(), [name]
        )
        assert wb.status == "COMPLETED"
        rows = list(
            es_client.cat.indices(index=name, format="json", expand_wildcards="all")
        )
        assert rows, f"index {name} missing after close"
        assert rows[0]["status"] == "close"
    finally:
        es_client.indices.delete(
            index=name, ignore_unavailable=True, expand_wildcards=["open", "closed"]
        )


def test_relocate_all_quiet_cluster(es_client) -> None:
    """Relocate mode=all is done when nothing is moving."""
    name = _create_index(es_client, "itest_relocate")
    try:
        waiter = Relocate(es_client, indices=[name], mode="all")
        assert waiter.check() is True
    finally:
        es_client.indices.delete(index=name, ignore_unavailable=True)


def test_action_run_reindex_waits_on_task(es_client) -> None:
    """ActionRun ReindexIndices waits on a live GET /_tasks/{id} payload."""
    src = _create_index(
        es_client,
        "itest_reindex-src",
        settings={"number_of_shards": 1, "number_of_replicas": 0},
    )
    dest = "itest_reindex-dest"
    try:
        for i in range(10):
            es_client.index(index=src, id=str(i), document={"n": i})
        es_client.indices.refresh(index=src)
        assert es_client.count(index=src)["count"] == 10

        wb = ActionRun(es_client, EventBus(), "es-checkpoint").run(
            ReindexIndices(dest), [src], timeout=60.0
        )

        assert wb.status == "COMPLETED"
        assert [s.name for s in wb.jobs[0].steps] == ["execute-1", "wait-1"]
        es_client.indices.refresh(index=dest)
        assert es_client.count(index=dest)["count"] == 10
    finally:
        es_client.indices.delete(index=src, ignore_unavailable=True)
        es_client.indices.delete(index=dest, ignore_unavailable=True)


def test_redact_ilm_run_clones_applies_confirms(es_client) -> None:
    """RedactIlm.run clone → apply → confirm against a live ILM poller."""
    es_client.cluster.put_settings(
        persistent={"indices.lifecycle.poll_interval": "1s"}
    )
    policy_name = "itest-logs"
    clone_name = "es-tools-itest-logs---v001"
    policy = {
        "phases": {
            "hot": {
                "min_age": "0ms",
                "actions": {"set_priority": {"priority": 100}},
            }
        }
    }
    es_client.ilm.put_lifecycle(name=policy_name, policy=policy)
    src = _create_index(
        es_client,
        "itest_ilm-src",
        settings={
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "index.lifecycle.name": policy_name,
        },
    )
    mounted = _create_index(
        es_client,
        "itest_ilm-mounted",
        settings={"number_of_shards": 1, "number_of_replicas": 0},
    )
    try:
        deadline = time.time() + 30
        info: dict = {}
        while time.time() < deadline:
            body = es_client.ilm.explain_lifecycle(index=src)
            info = (body.get("indices") or {}).get(src) or {}
            if info.get("managed"):
                break
            time.sleep(0.5)
        else:
            raise AssertionError(f"source never ILM-managed: {info}")

        wb = RedactIlm(es_client, EventBus(), "es-checkpoint").run(src, mounted)

        assert wb is not None
        assert wb.status == "COMPLETED"
        assert [s.name for s in wb.jobs[0].steps] == [
            "wait-new-1",
            "move-1",
            "wait-target-1",
        ]
        cloned = es_client.ilm.get_lifecycle(name=clone_name)
        assert clone_name in cloned
        settings = es_client.indices.get_settings(index=mounted)
        life = settings[mounted]["settings"]["index"].get("lifecycle") or {}
        assert life.get("name") == clone_name
        explain = es_client.ilm.explain_lifecycle(index=mounted)
        mounted_info = explain["indices"][mounted]
        assert mounted_info.get("managed") is True
        assert mounted_info.get("phase") in {"hot", "warm", "cold", "frozen", "delete"}
    finally:
        es_client.indices.delete(index=src, ignore_unavailable=True)
        es_client.indices.delete(index=mounted, ignore_unavailable=True)
        for name in (clone_name, policy_name):
            try:
                es_client.ilm.delete_lifecycle(name=name)
            except Exception:
                pass
