"""es_tools.client module.

Elasticsearch client builder with schema validation.

This module provides utilities for building Elasticsearch client connections
with comprehensive configuration validation and CLI integration.

Example:
    >>> from es_tools.client import create_client
    >>> config = {"elasticsearch": {"client": {"hosts": ["http://localhost:9200"]}}}
    >>> client = create_client(config)
"""

from es_tools.exceptions import (
    ESToolConfigurationError,
    ESToolConnectionError,
    ESToolSchemaValidationError,
)

from .builder import create_client
from .config import ConfigParser
from .defaults import VERSION_MAX, VERSION_MIN
from .models import ClientConfig, ElasticsearchConfig, OtherSettings
from .schemacheck import validate_config
from .utils import (
    check_es_version,
    get_version,
    verify_ssl_paths,
    verify_url_schema,
)

__all__ = [
    "VERSION_MAX",
    "VERSION_MIN",
    "ClientConfig",
    "ConfigParser",
    "ESToolConfigurationError",
    "ESToolConnectionError",
    "ESToolSchemaValidationError",
    "ElasticsearchConfig",
    "OtherSettings",
    "check_es_version",
    "create_client",
    "get_version",
    "validate_config",
    "verify_ssl_paths",
    "verify_url_schema",
]
