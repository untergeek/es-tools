# es_tools Conventions

## Validation

- Public methods validate **values** at the boundary (empty, `< 0`)
- Raise `ValueError` for invalid arguments
- Do not `isinstance(x, T)` when the parameter is already annotated `T`
- Raise `ESToolConfigurationError` for config issues
- Validate early, before any work begins
- `client` is a required positional argument on every type that talks to ES
  (`Job`, `Step`, waiters, tools, `ActionRun`). Never default-construct
  `Elasticsearch()`. Never default `client=None`.
- Store poll interval as `poll_pause` when the class also has a `pause()`
  lifecycle method. Waiters may keep `self.pause: float`.
- Do not add unused `**kwargs` “just in case”. Forward only named fields.

## Error Handling

- Domain errors propagate as `ESTool*` types
- List-action operational failures are `ESToolActionError` (`ESToolException`); ctor args stay `ValueError`
- Catch `Exception` only at documented boundaries (storage backend, waiter loop, Close `delete_alias`). `ilm.get_lifecycle` catches `NotFoundError` only; other failures are `ESToolActionError`
- Log errors at appropriate level (debug for expected failures, warning for unexpected, error for failures)
- Always clean up resources in finally blocks

## Timeouts

- Constructor args for timeouts (pause, timeout)
- Document defaults in docstrings
- Use `time.time()` for elapsed checks
- Log timeout warnings before raising

## Logging

- Use `debug.lv1()` for entry/exit
- Use `debug.lv2()` for important operations
- Use `debug.lv3()` for detailed tracing
- Use `logger.info()` for user-facing messages
- Use `logger.warning()` for recoverable issues
- Use `logger.error()` for failures

## Decorators

- `@begin_end` on public methods that talk to ES or sleep/poll
- Not required on pure in-memory getters/setters
- Use `@begin_end()`, or pass `begin`/`end`/`debug_obj` only when you need non-default levels

## List actions

- Accept `list[str]`; reject empty lists before `Workbook.start()`
- URI-bound APIs use `chunk_names` (3072-byte CSV); body APIs (snapshot/restore) do not
- Always run via `ActionRun` (one Job, Steps per unit)
- `ActionRun.run(action)` is typed `Any`: `ListAction` is only the required `name`/`mode`/`wait_type`/`execute` shape for `_units`/`_wait`. Optional `pre_*` and snapshot repo/name are `getattr`. Protocol attribute invariance on `mode`/`wait_type` also blocks typing the public method. Do not add `# type: ignore`.
- Operational failures: `ESToolActionError` (parent `ESToolException`); ctor args: `ValueError`
- `ExecuteResult(ok=False)` fails the Step directly; `Exception` is only for unexpected ES errors
- Optional `pre_step_name(index, **opts) -> str | None`; `None` skips `pre_execute`
- Optional `execute_step_name(index, **opts) -> str`; default Step name is `execute-N`
- `pre_execute` is generic (not Close-only); default Step name is `pre-N`
- Close: `skip_flush=False`, `delete_aliases=False`; alias strip is its own Step
- Close `delete_alias` failures are logged and ignored (Curator-compatible)
- Alias: `UpdateAliases(alias, add=..., remove=...)`; one `update_aliases`; `extra_settings` on add only; remove skips non-holders
- Create: `CreateIndices(settings=..., mappings=..., aliases=..., ignore_existing=False)`; PER_ITEM; already-exists is success only when `ignore_existing`
- Rollover: `RolloverIndices(conditions, new_index=..., extra_settings=...)`; PER_ITEM on **alias** names; `wait_for_active_shards` is an ES param, not an ActionRun waiter
- Reindex: `ReindexIndices(dest, body_extra=...)`; PER_ITEM source→dest; `wait_for_completion=False` + `wait_type="task"`
- Shrink: `ShrinkIndices(shrink_node, ...)`; PER_ITEM pipeline (route → relocate wait → block writes → shrink → aliases/delete). Explicit node name; no DETERMINISTIC picker
- Cold2frozen: `Cold2FrozenIndices(...)`; PER_ITEM pipeline (inspect → mount → verify → aliases → delete). Snapshot coords from index settings; ILM/already-frozen fail inspect
- Relocate waiter: `mode="selected"` (default) waits until every shard copy of the given indices is STARTED (`UNASSIGNED` is not success). Optional `node` / `action.wait_node` / opts `wait_node` requires those copies STARTED on that node. `mode="all"` waits for cluster-wide `cluster.health` `relocating_shards==0`. `ActionRun` passes `wait_mode` via opts (or `action.wait_mode`)
- ILM waiters: `IlmPhase(index, phase)` / `IlmStep(index, step)`. Phase order is `new < hot < warm < cold < frozen < delete`; `IlmPhase` is done when current is the target **or later** (`phase='new'` means new-or-later). ActionRun `wait_type="ilm_phase"` needs one name + `phase` via opts or `action.ilm_phase`. `wait_type="ilm_step"` needs one name; `step` via opts / `action.ilm_step` (default `complete`)
- Step state-driven ILM: `check_type="ilm_phase"|"ilm_step"` requires `check_index` (index) and `check_value` (phase or step). Do not stuff the index into `check_value`
- ConfirmIlmPhase: `ConfirmIlmPhase(phase)` per mounted index; pipeline wait-new → move_to_step (skip if already target complete) → wait-target. Target phase is not `new`
- ApplyIlmPolicy: `ApplyIlmPolicy(lifecycle)` PUT `index.lifecycle` per index
- RedactIlm: clone source policy (`es-tools-{name}---vNNN` from one catalog GET, named GET before PUT so an occupied name is never overwritten, reuse matching body, verify after PUT; prune passed phases; `ClonedIlm.phase` is a ConfirmIlmPhase target, never `new`) → apply on mounted → ConfirmIlmPhase. Unmanaged source is a no-op. Does not restore/redact/mount. `confirmable_phase` failures, exhausted `---v001`–`---v999`, and empty `strip_ilm_name` remainder are `ESToolActionError`. `dry_run` still named-GETs (no PUT)
- Cluster routing: `SetClusterRouting(routing_type, setting, value)`; `whole_list`, one `cluster.put_settings(transient=...)`; `wait_type="relocate"` + `wait_mode="all"`; exported from `es_tools.cluster` only
- Delete retries leftovers (still `exists`) up to 3 times; client exceptions fail the Step immediately
- `@begin_end` on `execute` / `pre_execute`

## Type Hints

- Use `from __future__ import annotations` at module top
- Use concrete types where possible
- Use `X | None` for nullable parameters
- Use `X | Y` for multiple valid types
- `client.api_key` is `str | tuple[str, str] | None` (elasticsearch9). YAML two-item lists coerce to `(id, key)`. Reject empty string, wrong arity, and empty parts
- Timestamps: `datetime.now(UTC)`; import `UTC` from `datetime`
