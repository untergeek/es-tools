"""Mount cold searchable-snapshot indices as frozen (partial) mounts."""

from __future__ import annotations

from typing import Any

from es_tools.checkpoint.action_run import ExecuteResult, Mode, StepSpec
from es_tools.debug import begin_end
from es_tools.exceptions import ESToolActionError

_DEFAULT_IGNORE = ["index.refresh_interval"]


class Cold2FrozenIndices:
    """Migrate each cold searchable-snapshot index to a frozen partial mount.

    Per index, ActionRun emits: inspect → mount → verify → aliases → delete.
    Snapshot coordinates are read from the source index settings (not ILM).

    Args:
        index_settings: Extra settings applied when mounting.
        ignore_index_settings: Settings stripped on mount (default
            ``index.refresh_interval``).
        renamed_prefix: Prefix for the new index (default ``partial-``).
        transfer_aliases: Move aliases from source to the mount.
        delete_after: Delete the source index after a successful mount.

    Example:
        >>> ActionRun(client, bus, "es-checkpoint").run(
        ...     Cold2FrozenIndices(), ["logs-000001"]
        ... )
    """

    name = "cold2frozen"
    mode: Mode = "per_item"
    wait_type: str | None = None

    def __init__(
        self,
        *,
        index_settings: dict[str, Any] | None = None,
        ignore_index_settings: list[str] | None = None,
        renamed_prefix: str = "partial-",
        transfer_aliases: bool = True,
        delete_after: bool = True,
    ) -> None:
        if not renamed_prefix:
            raise ValueError("renamed_prefix must be a non-empty string")
        self.index_settings = index_settings
        self.ignore_index_settings = (
            list(ignore_index_settings)
            if ignore_index_settings is not None
            else list(_DEFAULT_IGNORE)
        )
        self.renamed_prefix = renamed_prefix
        self.transfer_aliases = transfer_aliases
        self.delete_after = delete_after

    def target_name(self, source: str) -> str:
        """Return the mounted index name for ``source``."""
        return f"{self.renamed_prefix}{source}"

    def pipeline(self, index: int, names: list[str], **opts: Any) -> list[StepSpec]:
        """Return the per-index Step list.

        Args:
            index: 1-based unit number.
            names: One-item unit (source index).
            **opts: Unused.

        Returns:
            Ordered StepSpec list for this index.
        """
        del names, opts
        specs = [
            StepSpec(f"inspect-{index}", op="inspect"),
            StepSpec(f"mount-{index}", op="mount"),
            StepSpec(f"verify-{index}", op="verify"),
        ]
        if self.transfer_aliases:
            specs.append(StepSpec(f"aliases-{index}", op="aliases"))
        if self.delete_after:
            specs.append(StepSpec(f"delete-{index}", op="delete"))
        return specs

    @begin_end()
    def execute(self, client: Any, names: list[str], **opts: Any) -> ExecuteResult:
        """Run inspect + mount (pipeline uses ``run_step``)."""
        del opts
        inspected = self._inspect(client, names[0])
        if not inspected.ok:
            return inspected
        return self._mount(client, names[0])

    @begin_end()
    def run_step(
        self, spec: StepSpec, client: Any, names: list[str], **opts: Any
    ) -> ExecuteResult:
        """Dispatch one pipeline op.

        Args:
            spec: Step from ``pipeline``.
            client: Elasticsearch client.
            names: One-item unit (source index).
            **opts: Unused.

        Returns:
            ExecuteResult for this op.

        Raises:
            ESToolActionError: If ``spec.op`` is unknown.
        """
        del opts
        source = names[0]
        if spec.op == "inspect":
            return self._inspect(client, source)
        if spec.op == "mount":
            return self._mount(client, source)
        if spec.op == "verify":
            return self._verify(client, source)
        if spec.op == "aliases":
            self._transfer_aliases(client, source)
            return ExecuteResult(ok=True, names=names)
        if spec.op == "delete":
            client.indices.delete(index=source)
            return ExecuteResult(ok=True, names=names)
        raise ESToolActionError(f"unknown cold2frozen op: {spec.op}")

    def _settings(self, body: dict[str, Any]) -> dict[str, Any]:
        return body.get("settings", {}).get("index", {})

    def _snapshot_coords(
        self, client: Any, source: str
    ) -> tuple[ExecuteResult | None, dict[str, Any], dict[str, Any]]:
        """GET source and return (error_result, store, aliases)."""
        body = client.indices.get(index=source)[source]
        settings = self._settings(body)
        lifecycle = settings.get("lifecycle") or {}
        if lifecycle.get("name"):
            return (
                ExecuteResult(
                    ok=False,
                    names=[source],
                    error=f"index {source} is associated with an ILM policy",
                ),
                {},
                {},
            )
        store = (settings.get("store") or {}).get("snapshot") or {}
        if not store:
            return (
                ExecuteResult(
                    ok=False,
                    names=[source],
                    error=f"index {source} is not a mounted searchable snapshot",
                ),
                {},
                {},
            )
        if store.get("partial") in {True, "true"}:
            return (
                ExecuteResult(
                    ok=False,
                    names=[source],
                    error=f"index {source} is already in the frozen tier",
                ),
                {},
                {},
            )
        repo = store.get("repository_name")
        snap = store.get("snapshot_name")
        snap_idx = store.get("index_name")
        if not repo or not snap or not snap_idx:
            return (
                ExecuteResult(
                    ok=False,
                    names=[source],
                    error=f"index {source} is missing snapshot coordinates",
                ),
                {},
                {},
            )
        return None, store, body.get("aliases") or {}

    def _inspect(self, client: Any, source: str) -> ExecuteResult:
        err, _, _ = self._snapshot_coords(client, source)
        if err is not None:
            return err
        return ExecuteResult(ok=True, names=[source])

    def _mount(self, client: Any, source: str) -> ExecuteResult:
        err, store, _ = self._snapshot_coords(client, source)
        if err is not None:
            return err
        kwargs: dict[str, Any] = {
            "repository": store["repository_name"],
            "snapshot": store["snapshot_name"],
            "index": store["index_name"],
            "renamed_index": self.target_name(source),
            "storage": "shared_cache",
            "wait_for_completion": True,
            "ignore_index_settings": self.ignore_index_settings,
        }
        if self.index_settings is not None:
            kwargs["index_settings"] = self.index_settings
        raw = client.searchable_snapshots.mount(**kwargs)
        return ExecuteResult(ok=True, names=[source], raw=raw)

    def _verify(self, client: Any, source: str) -> ExecuteResult:
        target = self.target_name(source)
        body = client.indices.get(index=target)[target]
        settings = self._settings(body)
        store = (settings.get("store") or {}).get("snapshot") or {}
        if store.get("partial") not in {True, "true"}:
            return ExecuteResult(
                ok=False,
                names=[source],
                error=f"index {target} is not a frozen searchable snapshot",
            )
        return ExecuteResult(ok=True, names=[source])

    def _transfer_aliases(self, client: Any, source: str) -> None:
        body = client.indices.get(index=source)[source]
        aliases = body.get("aliases") or {}
        target = self.target_name(source)
        actions: list[dict[str, Any]] = []
        for alias in aliases:
            actions.append({"remove": {"index": source, "alias": alias}})
            actions.append({"add": {"index": target, "alias": alias}})
        if actions:
            client.indices.update_aliases(actions=actions)
