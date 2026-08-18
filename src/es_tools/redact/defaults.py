"""Default configuration values for es_tools.redact."""

from typing import Any

TRACKING_INDEX: str = "redactions-tracker"

PHASES: tuple[str, ...] = ("hot", "warm", "cold", "frozen", "delete")

PAUSE_DEFAULT: str = "9.0"
PAUSE_ENVVAR: str = "PII_TOOL_PAUSE"
TIMEOUT_DEFAULT: str = "7200.0"
TIMEOUT_ENVVAR: str = "PII_TOOL_TIMEOUT"

TIMINGS: dict[str, Any] = {
    "exists": {
        "pause": 0.3,
        "timeout": 10.0,
    },
    "health": {
        "pause": 0.3,
        "timeout": 10.0,
    },
    "ilm": {
        "pause": 1.0,
        "timeout": 30.0,
    },
    "relocate": {
        "pause": 0.5,
        "timeout": 30.0,
    },
    "restore": {
        "pause": 0.5,
        "timeout": 30.0,
    },
    "snapshot": {
        "pause": 0.5,
        "timeout": 30.0,
    },
    "task": {
        "pause": 0.3,
        "timeout": 30.0,
    },
}


def index_settings() -> dict[str, Any]:
    """Return Elasticsearch index settings for the tracking index."""
    return {
        "index": {
            "number_of_shards": "1",
            "auto_expand_replicas": "0-1",
        }
    }


def status_mappings() -> dict[str, Any]:
    """Return Elasticsearch index mappings for the tracking index."""
    return {
        "properties": {
            "job": {"type": "keyword"},
            "task": {"type": "keyword"},
            "step": {"type": "keyword"},
            "join_field": {"type": "join", "relations": {"job": "task"}},
            "cleanup": {"type": "keyword"},
            "completed": {"type": "boolean"},
            "end_time": {"type": "date"},
            "errors": {"type": "boolean"},
            "dry_run": {"type": "boolean"},
            "index": {"type": "keyword"},
            "logs": {"type": "text"},
            "start_time": {"type": "date"},
        },
        "dynamic_templates": [
            {
                "configuration": {
                    "path_match": "config.*",
                    "mapping": {"type": "keyword", "index": False},
                }
            }
        ],
    }


def redaction_schema() -> dict[str, Any]:
    """Return the full schema for a redaction file."""
    return {
        "redactions": [
            {
                "pattern": {"type": "string", "required": True},
                "query": {"type": "object", "required": True},
                "fields": {"type": "array", "required": True},
                "message": {"type": "string", "default": "REDACTED"},
                "delete": {"type": "boolean", "default": True},
                "expected_docs": {"type": "integer", "min": 1, "max": 32768},
            }
        ]
    }
