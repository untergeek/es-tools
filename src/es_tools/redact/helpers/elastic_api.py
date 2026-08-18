"""Elasticsearch API helpers for es_tools.redact.

Provides helper functions for Elasticsearch search operations.

Example:
    >>> from es_tools.redact.helpers.elastic_api import do_search
    >>> result = do_search(client, "my_index", {"match_all": {}})
"""

import logging
from typing import Any

from es_tools.debug import debug

logger = logging.getLogger(__name__)


def do_search(
    client: Any,
    index: str,
    query: dict[str, Any],
    size: int = 10000,
    aggs: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Perform a search on Elasticsearch.

    Executes a search query on the specified index with optional aggregations.

    Args:
        client: Elasticsearch client.
        index: Index name or pattern.
        query: Search query.
        size: Maximum number of results (default: 10000).
        aggs: Aggregations to perform.
        **kwargs: Additional parameters.

    Returns:
        Search response dictionary.

    Example:
        >>> result = do_search(client, "my_index", {"match_all": {}})
        >>> result["hits"]["total"]["value"]
        100
    """
    debug.lv2(f"Performing search on {index}")
    body: dict[str, Any] = {
        "query": query,
        "size": size,
    }
    if aggs:
        body["aggs"] = aggs
    body.update(kwargs)

    response = client.search(index=index, body=body)
    return response
