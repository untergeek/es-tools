# Changelog

All notable changes to `es_tools` will be documented in this file.

## [Unreleased]

### Added

- `PatternFilter` with `target="snapshot"` lists snapshot names via `snapshot.get` (`SelectContext.repository` required). `SnapshotIndicesFilter` remains restore-universe (`target="index"`).
- `SnapshotIndicesFilter`: index names inside one snapshot (`snapshot.get`). Needs `SelectContext.repository` and `.snapshot`. `target="index"`. Not root-exported.
- `DeleteDataStreams` and `RolloverDataStreams` (stream names, `expand="none"`). Not root-exported. Data-stream rollover has no `new_index`.
- `Progress` EventBus event from `RedactFields` hit-loop. Not journaled. `ActionRun` passes `event_bus` in execute opts.
- Checkpoint tracking index is created with date mappings for `timestamp` and `@timestamp`. Indexed docs copy `@timestamp` from `timestamp`.
- `RedactFields` list action: hot-index `update_by_query` (async + task wait). Real mutation; dry_run is ActionRun's. `build_script` for Painless field overwrite. Not root-exported.
- `es-tools[cli]`: Click kit from es_client HEAD (`option_wrapper`, `OPTION_DEFAULTS`, `SHOW_EVERYTHING`, `options_from_dict`, `show_all_options`, `get_client` via `create_client`). Library `create_client` stays click-free.
- `PromoteIlm` list action: advance one ILM phase (`inspect` → `move` → `wait-target`). Last phase (`delete`) is a no-op. Unmanaged indices fail the inspect Step. Not root-exported.
- `es_tools.select`: pattern, alias, query, data_stream, and snapshot_indices selectors (`apply_filters`). Not exported from the package root. Alias/data-stream/query/snapshot `NotFoundError` is `[]`. Empty prefix/suffix requires `allow_unbounded`. `target="snapshot"` has no snapshot-name selector (`_KIND_TARGETS` rejects).
- `check_es_version(client, version_min=VERSION_MIN, version_max=VERSION_MAX)` opt-in cluster version gate. `create_client` does not call it. `VERSION_MAX` is exported.
- `IlmPhase` treats the target as “this phase or later” (`new` includes frozen).
- `Step.check_index` so `ilm_phase` / `ilm_step` are not jammed into `check_value`.
- `ConfirmIlmPhase`, `ApplyIlmPolicy`, `clone_ilm_policy`, and `RedactIlm` (clone → apply → confirm).
- Docker integration test for `RedactIlm.run` (clone → apply → confirm) against ElasticsearchDocker.
- Regression coverage for waiter exception accounting, restore mixed-shard completion, and `ReindexTask` polling error taxonomy.

### Fixed

- `Progress.job_id` is set from `ActionRun` execute opts (`job.job_id`). Direct `execute()` still leaves it empty.
- `wait.Task` treats nonempty `response.failures` as failure for every task action (not only reindex), so `update_by_query` cannot complete with leftover errors.
- `count_hits` raises `ESToolActionError` when the search body has no recognizable `hits.total` (does not treat a malformed response as zero hits).
- `RedactFields` loops until matching hits are 0 (or fails after 11 stagnant iterations). Missing task id fails execute. Empty dotted field names rejected.

### Changed

- CI `basedpyright src` no longer fails the `unit` job on pre-existing warnings (`failOnWarnings = false`). Type errors still fail.
- Result snapshots include the Step name (`step`) so pre_execute and execute rows are distinct.
- `ActionRun` snapshots each unit’s `ExecuteResult` onto `workbook.results` (JSON-safe `raw`). `_finish` passes them to `Workbook.complete`. `rolled_over: false` stays COMPLETED.
- `apply_filters` no longer special-cases `target="snapshot"`. Kinds reject it via `_KIND_TARGETS`. `SnapshotIndicesFilter` is `target="index"`.
- `PromoteIlm` skips a data stream's current write backing index (no wait, no `move_to_step`).
- `ActionRun(..., persist=False)` (library default) does not construct `ElasticsearchBackend`. `persist=True` subscribes a backend on the given EventBus. CLI/app must persist.
- ActionRun wait types dispatch through `es_tools.wait.dispatch.wait_on`. `get_version` (client) raises `ESToolVersionError` instead of returning `(0, 0, 0)`.
- `ActionRun.run` uses `_run_named_step` / `_stop_unit`; wait types dispatch through a private registry. `create_client` splits config/auth/transport. `clone_ilm_policy` splits source-policy lookup and phase prune. Behavior unchanged.
- Renamed `es_tools.snapshot.MultiTool` to `SnapshotTool`.
- `wait.Restore` now polls `indices.recovery` (no `task_id`).
- Waiters now count polling exceptions exactly once per failure, so `max_exceptions` reflects the configured retry budget.
- `wait.Restore` completion now keys off matching restore shards only, so unrelated same-index peer recovery does not keep restores waiting.
- `ReindexTask` now maps true task-missing 404s to `ESToolTaskNotFoundError` and other `tasks.get()` failures to `ESToolReindexError`.
- `client.api_key` accepts `str | tuple[str, str]` (ES9 `Elasticsearch(api_key=...)`). YAML two-item lists coerce to `(id, key)`.
- `clone_ilm_policy` loads ILM policies in one `get_lifecycle()` call, reuses a matching `---vNNN` body, verifies after `put_lifecycle`, and sets `ClonedIlm.phase` to a `ConfirmIlmPhase` target (`new` → earliest remaining phase). `ilm.get_lifecycle` 404 is empty; other failures are `ESToolActionError`.
- `strip_ilm_name` strips only leading `es-tools-` / `pii-tool-` prefixes (repeated), not mid-string matches.
- `confirmable_phase` raises `ESToolActionError` (not `ValueError`).
- `_choose_clone_name` named-GETs before `put_lifecycle` (does not overwrite an occupied name) and raises `ESToolActionError` when `---v001`–`---v999` are exhausted.
- `clone_ilm_policy` raises `ESToolActionError` when `strip_ilm_name` leaves an empty stub (no `es-tools----vNNN`). Dry-run still named-GETs before claiming a clone name.
- `wait.utils.response_dict` checks dict-ness without a TypeGuard so basedpyright does not treat keys/values as `Unknown`.

### Removed

- Hollow stubs: `FieldUsageAnalyzer`, `TimeSlicer`, `es_tools.testbed`, `RedactTool`, and no-op `redacters`. Keep `RedactIlm`.
- Stub-only exceptions: `ESToolTestbedException`, `ESToolIndexCreationError`, `ESToolSnapshotError`, `ESToolTestDataError`, `ESToolFieldUsageError`, `ESToolTimeSliceError`, `ESToolIndexNotFoundError`, `ESToolIndexException`.
- `create_client` parameters `version_min` / `version_max`. `skip_version_test` on client `other_settings`.
- `SecretStore` (unused in-memory Fernet wrapper). `create_client` already forwards `api_key` / `basic_auth` / `bearer_auth`. Dropped runtime dependency `cryptography`.
- Unused packaging: runtime `ecs_logging`; `dev` extras `click`, `tomli` (3.11+ has `tomllib`), and `pytest-asyncio`.

## [1.0.0] - 2024-08-15

Never published. The original "Initial Release" inventory claimed APIs that
were never real (`Builder`, `SecretStore`, `keeper`, `PiiTool`,
`FieldUsageAnalyzer`, `TimeSlicer`, `TestBed`, a Click `es-tools` CLI).
See **[Unreleased]** for what this tree actually contains.
