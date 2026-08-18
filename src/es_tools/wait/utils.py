"""Utility functions for es_tools.wait."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _is_dict(value: object) -> bool:
    """``isinstance`` without TypeGuard, so the subject stays ``Any``."""
    return isinstance(value, dict)


def response_dict(raw: Any) -> dict[str, Any]:
    """Normalize an ES client response to a plain dict."""
    src: Any = raw
    if not _is_dict(src):
        src = getattr(raw, "body", None)
        if not _is_dict(src):
            return {}
    return {str(k): v for k, v in src.items()}


def prettystr(obj: Any) -> str:
    """Convert an object to a pretty string representation.

    Args:
        obj: Object to convert.

    Returns:
        str: Pretty string representation.
    """
    try:
        import json

        return json.dumps(obj, indent=2, default=str)
    except (TypeError, ValueError):
        return str(obj)


def health_report(client: Any) -> None:
    """Log a health report from the Elasticsearch cluster.

    Args:
        client: Elasticsearch client instance.
    """
    try:
        health = client.cluster.health()
        logger.info(
            "Cluster health: status=%s, number_of_nodes=%d, active_shards=%d",
            health.get("status", "unknown"),
            health.get("number_of_nodes", 0),
            health.get("active_shards", 0),
        )
    except Exception as exc:
        logger.error("Unable to get health report: %s", exc)
