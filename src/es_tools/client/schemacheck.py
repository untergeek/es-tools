"""Schema validation for es_tools.client.

Validates configuration against expected schemas.
"""

import logging
from typing import Any

from es_tools.exceptions import ESToolSchemaValidationError
from es_tools.utils.helpers import redact

logger = logging.getLogger(__name__)


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate configuration against expected schema.

    Args:
        config: Configuration dictionary to validate.

    Returns:
        Validated configuration dictionary.

    Raises:
        ESToolSchemaValidationError: If configuration is invalid.

    Example:
        >>> config = {'elasticsearch': {'client': {'hosts': ['http://localhost:9200']}}}
        >>> validate_config(config)
        {'elasticsearch': {'client': {'hosts': ['http://localhost:9200']}}}
    """
    logger.debug("Validating configuration")

    # Check required keys
    if "elasticsearch" not in config:
        raise ESToolSchemaValidationError(
            "Configuration must contain 'elasticsearch' key"
        )

    if "client" not in config["elasticsearch"]:
        raise ESToolSchemaValidationError(
            "Configuration must contain 'elasticsearch.client' key"
        )

    client_config = config["elasticsearch"]["client"]

    # Check hosts
    if "hosts" in client_config:
        hosts = client_config["hosts"]
        if not isinstance(hosts, list):
            raise ESToolSchemaValidationError("'hosts' must be a list")
        if len(hosts) == 0:
            raise ESToolSchemaValidationError("'hosts' cannot be empty")

        # Validate each host URL
        from .utils import verify_url_schema

        validated_hosts = []
        for host in hosts:
            try:
                validated_hosts.append(verify_url_schema(host))
            except ValueError as exc:
                raise ESToolSchemaValidationError(f"Invalid host URL: {exc}") from exc

        client_config["hosts"] = validated_hosts

    # Check cloud_id
    if client_config.get("cloud_id"):
        if client_config.get("hosts"):
            raise ESToolSchemaValidationError(
                "Cannot specify both 'hosts' and 'cloud_id'"
            )

    # Filter sensitive fields
    config["elasticsearch"]["client"] = redact(client_config)

    logger.debug("Configuration validated successfully")
    return config
