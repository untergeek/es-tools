"""Clone an index's ILM policy, pruning phases already passed."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any

from elasticsearch9 import NotFoundError

from es_tools.exceptions import ESToolActionError
from es_tools.wait.ilm import PHASE_ORDER, explain_index
from es_tools.wait.utils import response_dict

_PREFIXES = ("es-tools-", "pii-tool-")
_VER = re.compile(r"^(.*)---v\d{3}$")


@dataclass(frozen=True)
class ClonedIlm:
    """Result of cloning a source index's ILM policy."""

    name: str
    phase: str
    policy: dict[str, Any]
    lifecycle: dict[str, Any]


def strip_ilm_name(name: str) -> str:
    """Strip leading es-tools-/pii-tool- prefixes and trailing ---vNNN."""
    out = name
    changed = True
    while changed:
        changed = False
        for prefix in _PREFIXES:
            if out.startswith(prefix):
                out = out.removeprefix(prefix)
                changed = True
    match = _VER.match(out)
    if match:
        out = match.group(1)
    return out


def _lifecycle_settings(client: Any, index: str) -> dict[str, Any]:
    body = response_dict(client.indices.get_settings(index=index))
    idx = body.get(index) or {}
    if not isinstance(idx, dict):
        return {}
    settings = idx.get("settings") or {}
    if not isinstance(settings, dict):
        return {}
    index_settings = settings.get("index") or {}
    if not isinstance(index_settings, dict):
        return {}
    lifecycle = index_settings.get("lifecycle") or {}
    return dict(lifecycle) if isinstance(lifecycle, dict) else {}


def _lifecycle_map(client: Any, name: str | None = None) -> dict[str, Any]:
    """Return ILM policies keyed by name.

    ``NotFoundError`` (HTTP 404) is an empty map. Any other exception is
    ``ESToolActionError``.
    """
    try:
        raw = (
            client.ilm.get_lifecycle(name=name)
            if name is not None
            else client.ilm.get_lifecycle()
        )
    except NotFoundError:
        return {}
    except Exception as exc:
        raise ESToolActionError(f"ilm.get_lifecycle failed: {exc}") from exc
    return response_dict(raw)


def _policy_body(entry: object) -> dict[str, Any]:
    if not isinstance(entry, dict):
        return {}
    body = entry.get("policy")
    return dict(body) if isinstance(body, dict) else {}


def confirmable_phase(current: str, phases: dict[str, Any]) -> str:
    """Return the ConfirmIlmPhase target for a cloned policy."""
    if current != "new" and current in phases:
        return current
    if current in ("", "new") or current not in PHASE_ORDER:
        for name in PHASE_ORDER:
            if name != "new" and name in phases:
                return name
        raise ESToolActionError(
            f"cloned ILM policy has no confirmable phase (current={current!r}, "
            f"phases={sorted(phases)})"
        )
    raise ESToolActionError(
        f"cloned ILM policy missing current phase {current!r}; "
        f"phases={sorted(phases)}"
    )


def _choose_clone_name(
    client: Any,
    stub: str,
    policy: dict[str, Any],
    catalog: dict[str, Any],
    *,
    dry_run: bool,
) -> str:
    occupied = dict(catalog)
    for ver in range(1, 1000):
        chosen = f"{stub}---v{ver:03}"
        existing = _policy_body(occupied.get(chosen))
        if not existing:
            existing = _policy_body(_lifecycle_map(client, chosen).get(chosen))
            if existing:
                occupied[chosen] = {"policy": existing}
        if existing == policy:
            return chosen
        if existing:
            continue
        if dry_run:
            return chosen
        try:
            client.ilm.put_lifecycle(name=chosen, policy=policy)
        except Exception as exc:
            raise ESToolActionError(
                f"ilm.put_lifecycle failed for {chosen!r}: {exc}"
            ) from exc
        written = _policy_body(_lifecycle_map(client, chosen).get(chosen))
        if written == policy:
            return chosen
        occupied[chosen] = {"policy": written or {"_mismatch": True}}
    raise ESToolActionError(f"no free ILM clone name under {stub}")


def _source_policy(
    catalog: dict[str, Any], src_name: str
) -> dict[str, Any] | None:
    entry = catalog.get(str(src_name)) or {}
    if not isinstance(entry, dict):
        return None
    policy = copy.deepcopy(entry.get("policy") or {})
    if not isinstance(policy, dict) or not policy:
        return None
    return policy


def _prune_passed_phases(phase: str, policy: dict[str, Any]) -> dict[str, Any]:
    phases = dict(policy.get("phases") or {})
    if phase in PHASE_ORDER:
        here = PHASE_ORDER.index(phase)
        phases = {
            name: body
            for name, body in phases.items()
            if name not in PHASE_ORDER or PHASE_ORDER.index(name) >= here
        }
    out = dict(policy)
    out["phases"] = phases
    return out


def clone_ilm_policy(
    client: Any, index: str, *, dry_run: bool = False
) -> ClonedIlm | None:
    """Clone ``index``'s ILM policy if managed; otherwise ``None``.

    Args:
        client: Elasticsearch client.
        index: Source index whose policy to clone.
        dry_run: If True, choose a clone name but do not ``put_lifecycle``.

    Returns:
        Cloned policy metadata, or ``None`` if the index has no lifecycle.
    """
    lifecycle = _lifecycle_settings(client, index)
    src_name = lifecycle.get("name")
    if not src_name:
        return None
    catalog = _lifecycle_map(client)
    policy = _source_policy(catalog, str(src_name))
    if policy is None:
        return None
    info = explain_index(client, index)
    phase = str(info.get("phase") or "")
    policy = _prune_passed_phases(phase, policy)
    target = confirmable_phase(phase, policy.get("phases") or {})
    stripped = strip_ilm_name(str(src_name))
    if not stripped:
        raise ESToolActionError(f"stripped ILM name is empty ({src_name!r})")
    stub = f"es-tools-{stripped}"
    chosen = _choose_clone_name(client, stub, policy, catalog, dry_run=dry_run)
    new_lifecycle = dict(lifecycle)
    new_lifecycle["name"] = chosen
    return ClonedIlm(name=chosen, phase=target, policy=policy, lifecycle=new_lifecycle)
