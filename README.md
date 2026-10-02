# es_tools

Unified Elasticsearch tools library: client construction, waiters, checkpointed list actions, and related helpers.

## Overview

- **Client**: `create_client` with schema validation
- **Wait**: Health, Exists, Relocate, Restore, Snapshot, Task, ILM phase/step
- **Checkpoint**: Workbook / Job / Step and `ActionRun`
- **Index actions**: open, close, delete, data-stream delete/rollover, settings, shrink, reindex, ILM confirm, …
- **Snapshot**: `SnapshotTool` and snapshot list actions
- **Reindex**: `ReindexTask` / `ReindexMonitor`
- **Redact**: `RedactIlm` (clone / apply / confirm)
- **Docker**: `ElasticsearchDocker` for tests
- **Select**: `es_tools.select` pattern/alias/query/data_stream/snapshot_indices name lists; `PatternFilter` + `target="snapshot"` lists snapshot names
- **CLI extra**: `es-tools[cli]` Click option kit (`es_tools.client.cli`)
- **Utils**: lists, chunking, config helpers

## Installation

From source:

```bash
cd /path/to/es-tools
uv sync
```

## Quick Start

```python
from es_tools.client import create_client
from es_tools.checkpoint import ActionRun, EventBus
from es_tools.index.actions import OpenIndices
from es_tools.wait import Health

client = create_client(
    {"elasticsearch": {"client": {"hosts": ["http://localhost:9200"]}}}
)

Health(client).wait()

wb = ActionRun(client, EventBus(), "es-checkpoint").run(
    OpenIndices(), ["logs-1", "logs-2"]
)
```

## Modules

### Client (`es_tools.client`)

```python
from es_tools.client import create_client, ConfigParser, validate_config

config = validate_config(
    {"elasticsearch": {"client": {"hosts": ["http://localhost:9200"]}}}
)
client = create_client(config)
```

### Wait (`es_tools.wait`)

```python
from es_tools.wait import Exists, Health, IlmPhase, Relocate, Restore, Snapshot, Task

Exists(client, index="my_index").wait()
Health(client, check_type="status").wait()
Task(client, task_id="my_task_id").wait()
```

### Checkpoint (`es_tools.checkpoint`)

```python
from es_tools.checkpoint import ActionRun, EventBus
from es_tools.index.actions import OpenIndices

run = ActionRun(client, EventBus(), "es-checkpoint")
workbook = run.run(OpenIndices(), ["logs-1", "logs-2"])
# Journal writes: ActionRun(..., persist=True)
```

### Snapshot (`es_tools.snapshot`)

```python
from es_tools.snapshot import SnapshotTool

tool = SnapshotTool(client)
tool.snapshot("my_snapshot", repository="my_repo")
```

### Reindex (`es_tools.reindex`)

```python
from es_tools.reindex import ReindexTask, ReindexMonitor

task = ReindexTask(client, task_id="abc123")
task.wait_for_completion()
```

### Index (`es_tools.index`)

List actions such as `OpenIndices`, `CloseIndices`, `DeleteIndices`, `ConfirmIlmPhase`, `PromoteIlm`.
Run them through `ActionRun`.

### Redact (`es_tools.redact`)

```python
from es_tools.redact import RedactIlm

RedactIlm(client, EventBus(), "es-checkpoint").run(source_index, mounted_index)
```

`es_tools.redact` exports `RedactFields`.

### Cluster (`es_tools.cluster`)

`es_tools.cluster` exports `SetClusterRouting`.

### Select (`es_tools.select`)

```python
from es_tools.select import PatternFilter, SelectContext, apply_filters

ctx = SelectContext(client=client, target="index")
names = apply_filters(ctx, [PatternFilter(pattern_kind="prefix", value="logs-")])
```

### Docker (`es_tools.docker`)

`ElasticsearchDocker()` uses `docker.elastic.co/elasticsearch/elasticsearch:9.5.2`
by default. Override with `ES_TOOLS_DOCKER_IMAGE`.

```python
from es_tools.docker import ElasticsearchDocker

docker = ElasticsearchDocker()
docker.start()
client = docker.get_client()
```

### Utils (`es_tools.utils`)

```python
from es_tools.utils import (
    ensure_list, get_version,
    log_exception, pluralize, redact, to_bool, to_int, to_str,
    ConfigManager, load_config, save_config
)
```

`get_version()` works only when the `es-tools` distribution is installed.

## Testing

```bash
cd /path/to/es-tools
uv run pytest tests/unit -v
```

Docker-marked tests need a local Docker daemon.

## Building

```bash
cd /path/to/es-tools
uv build
```

## Dependencies

- `elasticsearch9>=9.0.0`
- `pydantic>=2.0.0`
- `pyyaml>=6.0`
- `tiered_debug>=1.5.1`

## License

Apache 2.0

## Author

Aaron Mildenstein
