"""es_tools.docker module.

Docker test infrastructure for Elasticsearch.

Provides utilities for running Elasticsearch in Docker containers
for testing purposes.

Example:
    >>> from es_tools.docker import ElasticsearchDocker
    >>> docker = ElasticsearchDocker()
    >>> docker.start()
    >>> client = docker.get_client()
"""

from .docker import ElasticsearchDocker

__all__ = [
    "ElasticsearchDocker",
]
