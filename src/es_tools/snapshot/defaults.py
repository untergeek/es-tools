"""Default configuration values for es_tools.snapshot."""

from typing import Any

SNAPSHOT_SETTINGS: dict[str, Any] = {
    "timeout": "30m",
    "wait_for_completion": True,
    "max_concurrent_snapshots": 5,
}

REPOSITORY_SETTINGS: dict[str, Any] = {
    "type": "fs",
    "location": "/mnt/backups",
    "compress": True,
}
