"""Tests for ILM policy clone + name stripping."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from elastic_transport import ApiResponseMeta, HttpHeaders
from elasticsearch9 import NotFoundError

from es_tools.exceptions import ESToolActionError
from es_tools.index.ilm import (
    _prune_passed_phases,
    _source_policy,
    clone_ilm_policy,
    strip_ilm_name,
)


def _not_found() -> NotFoundError:
    meta = ApiResponseMeta(
        status=404,
        http_version="1.1",
        headers=HttpHeaders(),
        duration=0.0,
        node=None,  # type: ignore
    )
    return NotFoundError(
        "not found", meta, {"error": {"type": "resource_not_found_exception"}}
    )


def _src_settings(name: str = "logs") -> dict:
    return {"src": {"settings": {"index": {"lifecycle": {"name": name}}}}}


def _hot_cold_policy() -> dict:
    return {
        "phases": {
            "hot": {"actions": {}},
            "cold": {"actions": {"set_priority": {"priority": 0}}},
        }
    }


def _pruned_cold() -> dict:
    return {"phases": {"cold": {"actions": {"set_priority": {"priority": 0}}}}}


def _catalog_client(
    *,
    source_name: str = "logs",
    source_policy: dict | None = None,
    catalog: dict | None = None,
    explain_phase: str = "cold",
    put_stores: bool = True,
    overwrite_after_put: dict | None = None,
) -> MagicMock:
    """Mock ES so get_lifecycle() is a catalog; named get 404s when missing."""
    client = MagicMock()
    client.indices.get_settings.return_value = _src_settings(source_name)
    client.ilm.explain_lifecycle.return_value = {
        "indices": {
            "src": {"managed": True, "phase": explain_phase, "step": "complete"}
        }
    }
    store: dict = dict(catalog or {})
    if source_policy is not None:
        store[source_name] = {"policy": source_policy}

    def get_lifecycle(*, name: str | None = None, **_kw):
        if name is None:
            return {k: dict(v) for k, v in store.items()}
        if name not in store:
            raise _not_found()
        return {name: dict(store[name])}

    def put_lifecycle(*, name: str, policy: dict, **_kw):
        if overwrite_after_put is not None:
            store[name] = {"policy": dict(overwrite_after_put)}
            return
        if put_stores:
            store[name] = {"policy": policy}

    client.ilm.get_lifecycle.side_effect = get_lifecycle
    client.ilm.put_lifecycle.side_effect = put_lifecycle
    client._store = store
    return client


def test_strip_ilm_name_pii_and_es_tools() -> None:
    """Both historical pii-tool- and es-tools- prefixes strip with ---vNNN."""
    assert strip_ilm_name("pii-tool-logs---v003") == "logs"
    assert strip_ilm_name("es-tools-logs---v001") == "logs"
    assert strip_ilm_name("logs") == "logs"


def test_strip_ilm_name_keeps_midstring_prefix() -> None:
    """replace() would delete es-tools- in the middle of a real policy name."""
    assert strip_ilm_name("logs-es-tools-prod---v001") == "logs-es-tools-prod"


def test_strip_ilm_name_stacked_leading_prefixes() -> None:
    """Repeated leading clone prefixes still fully strip so stubs do not grow."""
    assert strip_ilm_name("es-tools-es-tools-logs---v001") == "logs"
    assert strip_ilm_name("pii-tool-es-tools-logs---v002") == "logs"


def test_strip_ilm_name_prefix_only_is_empty() -> None:
    """Prefix-only or ---vNNN-only names strip to empty (clone must reject)."""
    assert strip_ilm_name("es-tools-") == ""
    assert strip_ilm_name("pii-tool-") == ""
    assert strip_ilm_name("---v001") == ""
    assert strip_ilm_name("es-tools----v001") == ""


def test_clone_empty_stripped_name_is_action_error() -> None:
    """Do not emit es-tools----v001 from a prefix-only lifecycle name."""
    client = _catalog_client(
        source_name="es-tools-",
        source_policy=_hot_cold_policy(),
        explain_phase="cold",
    )
    with pytest.raises(ESToolActionError, match="stripped ILM name is empty"):
        clone_ilm_policy(client, "src")
    client.ilm.put_lifecycle.assert_not_called()


def test_clone_unmanaged_returns_none() -> None:
    """No lifecycle name means nothing to clone."""
    client = MagicMock()
    client.indices.get_settings.return_value = {"src": {"settings": {"index": {}}}}
    assert clone_ilm_policy(client, "src") is None


def test_clone_puts_pruned_policy() -> None:
    """Phases before the current explain phase are dropped."""
    client = _catalog_client(
        source_policy=_hot_cold_policy(),
        explain_phase="cold",
    )
    result = clone_ilm_policy(client, "src")
    assert result is not None
    assert result.name == "es-tools-logs---v001"
    assert result.phase == "cold"
    assert "hot" not in result.policy["phases"]
    assert "cold" in result.policy["phases"]
    client.ilm.put_lifecycle.assert_called_once()
    kwargs = client.ilm.put_lifecycle.call_args.kwargs
    assert kwargs["name"] == "es-tools-logs---v001"
    assert "hot" not in kwargs["policy"]["phases"]


def test_clone_dry_run_does_not_put() -> None:
    """dry_run still chooses a name but does not put_lifecycle."""
    client = _catalog_client(
        source_policy={"phases": {"cold": {"actions": {}}}},
        explain_phase="cold",
    )
    result = clone_ilm_policy(client, "src", dry_run=True)
    assert result is not None
    assert result.name == "es-tools-logs---v001"
    client.ilm.put_lifecycle.assert_not_called()


def test_clone_get_lifecycle_error_is_action_error() -> None:
    """Transport errors are not 'policy missing' / 'name free'."""
    client = MagicMock()
    client.indices.get_settings.return_value = _src_settings()
    client.ilm.get_lifecycle.side_effect = TimeoutError("boom")
    with pytest.raises(ESToolActionError, match="get_lifecycle"):
        clone_ilm_policy(client, "src")


def test_clone_get_lifecycle_404_is_missing() -> None:
    """NotFoundError on the catalog GET means no source policy to clone."""
    client = MagicMock()
    client.indices.get_settings.return_value = _src_settings()
    client.ilm.get_lifecycle.side_effect = _not_found()
    assert clone_ilm_policy(client, "src") is None


def test_clone_reuses_matching_version() -> None:
    """Same body at es-tools-logs---v001 is reused; no PUT."""
    pruned = _pruned_cold()
    client = _catalog_client(
        source_policy=_hot_cold_policy(),
        catalog={"es-tools-logs---v001": {"policy": pruned}},
        explain_phase="cold",
    )
    result = clone_ilm_policy(client, "src")
    assert result is not None
    assert result.name == "es-tools-logs---v001"
    client.ilm.put_lifecycle.assert_not_called()


def test_clone_bumps_version_when_body_differs() -> None:
    """Occupied v001 with a different body → v002."""
    client = _catalog_client(
        source_policy=_hot_cold_policy(),
        catalog={
            "es-tools-logs---v001": {"policy": {"phases": {"hot": {"actions": {}}}}}
        },
        explain_phase="cold",
    )
    result = clone_ilm_policy(client, "src")
    assert result is not None
    assert result.name == "es-tools-logs---v002"
    kwargs = client.ilm.put_lifecycle.call_args.kwargs
    assert kwargs["name"] == "es-tools-logs---v002"
    assert "hot" not in kwargs["policy"]["phases"]


def test_clone_put_race_retries_next_version() -> None:
    """If GET after PUT is not our policy, do not keep that name."""
    other = {"phases": {"delete": {"actions": {}}}}  # type: ignore
    client = _catalog_client(
        source_policy=_hot_cold_policy(),
        explain_phase="cold",
    )
    calls = {"n": 0}

    def put_lifecycle(*, name: str, policy: dict, **_kw):
        calls["n"] += 1
        if calls["n"] == 1:
            client._store[name] = {"policy": other}
        else:
            client._store[name] = {"policy": policy}

    client.ilm.put_lifecycle.side_effect = put_lifecycle
    result = clone_ilm_policy(client, "src")
    assert result is not None
    assert result.name == "es-tools-logs---v002"
    assert client.ilm.put_lifecycle.call_count == 2


def test_clone_named_get_before_put_skips_occupied() -> None:
    """Do not put_lifecycle over a name that a named GET shows as taken."""
    other = {"phases": {"delete": {"actions": {}}}}  # type: ignore
    client = _catalog_client(
        source_policy=_hot_cold_policy(),
        explain_phase="cold",
    )
    inner = client.ilm.get_lifecycle.side_effect

    def get_lifecycle(*, name: str | None = None, **kw):
        if name == "es-tools-logs---v001" and name not in client._store:
            client._store[name] = {"policy": other}
        return inner(name=name, **kw)

    client.ilm.get_lifecycle.side_effect = get_lifecycle
    result = clone_ilm_policy(client, "src")
    assert result is not None
    assert result.name == "es-tools-logs---v002"
    names = [c.kwargs["name"] for c in client.ilm.put_lifecycle.call_args_list]
    assert names == ["es-tools-logs---v002"]


def test_clone_dry_run_named_get_skips_occupied() -> None:
    """dry_run still named-GETs; does not claim a live occupied name or PUT."""
    other = {"phases": {"delete": {"actions": {}}}}  # type: ignore
    client = _catalog_client(
        source_policy=_hot_cold_policy(),
        explain_phase="cold",
    )
    inner = client.ilm.get_lifecycle.side_effect

    def get_lifecycle(*, name: str | None = None, **kw):
        if name == "es-tools-logs---v001" and name not in client._store:
            client._store[name] = {"policy": other}
        return inner(name=name, **kw)

    client.ilm.get_lifecycle.side_effect = get_lifecycle
    result = clone_ilm_policy(client, "src", dry_run=True)
    assert result is not None
    assert result.name == "es-tools-logs---v002"
    client.ilm.put_lifecycle.assert_not_called()


def test_clone_new_phase_confirms_first_remaining() -> None:
    """Explain phase 'new' is not a ConfirmIlmPhase target; use earliest remaining."""
    client = _catalog_client(
        source_policy=_hot_cold_policy(),
        explain_phase="new",
    )
    result = clone_ilm_policy(client, "src")
    assert result is not None
    assert result.phase == "hot"
    assert "hot" in result.policy["phases"]


def test_clone_rejects_when_current_phase_missing() -> None:
    """Do not confirm an earlier phase if explain is past it and it was pruned away."""
    client = _catalog_client(
        source_policy={"phases": {"delete": {"actions": {}}}},
        explain_phase="cold",
    )
    with pytest.raises(ESToolActionError, match="missing current phase"):
        clone_ilm_policy(client, "src")


def test_clone_rejects_when_no_confirmable_phase() -> None:
    """Empty cloned phases with explain 'new' is an action error."""
    client = _catalog_client(
        source_policy={"phases": {}},
        explain_phase="new",
    )
    with pytest.raises(ESToolActionError, match="no confirmable phase"):
        clone_ilm_policy(client, "src")


def test_clone_exhausted_versions_is_action_error() -> None:
    """v001-v999 occupied with a different body is ESToolActionError, not ValueError."""
    catalog = {
        f"es-tools-logs---v{ver:03}": {"policy": {"phases": {"hot": {"n": ver}}}}
        for ver in range(1, 1000)
    }
    client = _catalog_client(
        source_policy=_hot_cold_policy(),
        catalog=catalog,
        explain_phase="cold",
    )
    with pytest.raises(ESToolActionError, match="no free ILM clone name"):
        clone_ilm_policy(client, "src")
    client.ilm.put_lifecycle.assert_not_called()


def test_source_policy_none_on_empty() -> None:
    """Missing or empty catalog bodies are None (clone returns None)."""
    assert _source_policy({}, "logs") is None
    assert _source_policy({"logs": {"policy": {}}}, "logs") is None
    assert _source_policy({"logs": "nope"}, "logs") is None


def test_source_policy_deepcopy() -> None:
    """Mutating the returned policy must not change the catalog entry."""
    catalog = {"logs": {"policy": {"phases": {"hot": {"actions": {}}}}}}  # type: ignore
    policy = _source_policy(catalog, "logs")
    assert policy is not None
    policy["phases"]["hot"] = "mutated"
    assert catalog["logs"]["policy"]["phases"]["hot"] == {"actions": {}}


def test_prune_passed_phases_keeps_current_and_later() -> None:
    """Phases before the current PHASE_ORDER phase are dropped."""
    policy = {
        "phases": {
            "hot": {"actions": {}},
            "cold": {"actions": {"set_priority": {"priority": 0}}},
            "delete": {"actions": {}},
        }
    }
    out = _prune_passed_phases("cold", policy)
    assert set(out["phases"]) == {"cold", "delete"}
    assert "hot" not in out["phases"]


def test_prune_passed_phases_unknown_phase_keeps_all() -> None:
    """A phase not in PHASE_ORDER is not pruned."""
    policy = {"phases": {"hot": {}, "custom": {}}}  # type: ignore
    out = _prune_passed_phases("custom", policy)
    assert set(out["phases"]) == {"hot", "custom"}
