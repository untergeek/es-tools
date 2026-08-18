"""Factory function and utilities for creating Elasticsearch clients.

Replaces the Builder class with a functional approach using Pydantic models
and dataclasses for configuration management.
"""

import logging
from typing import Any

import elasticsearch9

from es_tools.exceptions import ESToolBuilderException, ESToolConfigurationError

from .defaults import ES_DEFAULT
from .models import ClientConfig, ElasticsearchConfig, OtherSettings
from .utils import (
    verify_ssl_paths,
    verify_url_schema,
)
from .validators import ElasticsearchConfigModel

logger = logging.getLogger(__name__)

# Error message constants
INVALID_HOST_SCHEMA = "Invalid host schema: {host}"
HOSTS_AND_CLOUD_ID_CONFLICT = 'Cannot populate both "hosts" and "cloud_id"'
MULTIPLE_HOSTS_MASTER_ONLY = (
    '"master_only" cannot be True if multiple hosts are specified. Hosts = {hosts}'
)


def _extract_config_from_dict(config_dict: dict[str, Any]) -> ElasticsearchConfig:
    """Extract and validate configuration from a dictionary.

    Args:
        config_dict: Configuration dictionary with 'elasticsearch' key.

    Returns:
        ElasticsearchConfig dataclass.

    Raises:
        ESToolConfigurationError: If configuration is invalid.
    """
    # Validate structure
    if "elasticsearch" not in config_dict:
        raise ESToolConfigurationError("Configuration must contain 'elasticsearch' key")

    es_config = config_dict["elasticsearch"]
    if "client" not in es_config:
        raise ESToolConfigurationError(
            "Configuration must contain 'elasticsearch.client' key"
        )

    # Convert to Pydantic model for validation
    try:
        pydantic_model = ElasticsearchConfigModel.model_validate(es_config)
    except Exception as e:
        raise ESToolConfigurationError(str(e)) from e

    # Convert Pydantic model to dataclasses
    client_config = ClientConfig(
        hosts=list(pydantic_model.client.hosts or []),
        cloud_id=pydantic_model.client.cloud_id,
        api_key=pydantic_model.client.api_key,
        basic_auth=pydantic_model.client.basic_auth,
        bearer_auth=pydantic_model.client.bearer_auth,
        verify_certs=pydantic_model.client.verify_certs,
        ca_certs=pydantic_model.client.ca_certs,
        client_cert=pydantic_model.client.client_cert,
        client_key=pydantic_model.client.client_key,
        request_timeout=pydantic_model.client.request_timeout,
    )

    other_settings = OtherSettings(
        username=pydantic_model.other_settings.username,
        password=pydantic_model.other_settings.password,
        master_only=pydantic_model.other_settings.master_only,
    )

    return ElasticsearchConfig(client=client_config, other_settings=other_settings)


def _validate_config(config: ElasticsearchConfig) -> None:
    """Validate configuration constraints.

    Args:
        config: Configuration dataclass.

    Raises:
        ESToolConfigurationError: If validation fails.
    """
    if config.client.hosts and config.client.cloud_id:
        raise ESToolConfigurationError(HOSTS_AND_CLOUD_ID_CONFLICT)

    if config.other_settings.master_only and len(config.client.hosts) > 1:
        raise ESToolConfigurationError(
            MULTIPLE_HOSTS_MASTER_ONLY.format(hosts=config.client.hosts)
        )


def _verify_host_schemas(hosts: list[str]) -> list[str]:
    """Verify and validate host URL schemas.

    Args:
        hosts: List of host URLs. Must not be empty.

    Returns:
        List of validated host URLs.

    Raises:
        ESToolConfigurationError: If hosts is empty or any host has invalid schema.
    """
    if not hosts:
        raise ESToolConfigurationError("hosts list cannot be empty")

    verified_hosts = []
    for host in hosts:
        try:
            verified_hosts.append(verify_url_schema(host))
        except ValueError as exc:
            logger.critical(INVALID_HOST_SCHEMA.format(host=host))
            raise ESToolConfigurationError(
                INVALID_HOST_SCHEMA.format(host=host)
            ) from exc
    return verified_hosts


def _with_client_hosts(
    es_config: ElasticsearchConfig, hosts: list[str] | None
) -> ElasticsearchConfig:
    src = es_config.client
    return ElasticsearchConfig(
        client=ClientConfig(
            hosts=hosts if hosts is not None else list(src.hosts or []),
            cloud_id=src.cloud_id,
            api_key=src.api_key,
            basic_auth=src.basic_auth,
            bearer_auth=src.bearer_auth,
            verify_certs=src.verify_certs,
            ca_certs=src.ca_certs,
            client_cert=src.client_cert,
            client_key=src.client_key,
            request_timeout=src.request_timeout,
        ),
        other_settings=es_config.other_settings,
    )


def _build_config(
    config: dict[str, Any] | None,
    configfile: str | None,
) -> ElasticsearchConfig:
    if configfile:
        from .utils import check_config, get_yaml

        raw_config = check_config(get_yaml(configfile))
    elif config:
        raw_config = config
    else:
        raw_config = ES_DEFAULT

    es_config = _extract_config_from_dict(raw_config)
    if es_config.client.hosts:
        es_config = _with_client_hosts(
            es_config, _verify_host_schemas(es_config.client.hosts)
        )
    _validate_config(es_config)
    if not es_config.client.hosts and not es_config.client.cloud_id:
        es_config = _with_client_hosts(es_config, ["http://127.0.0.1:9200"])
    return es_config


def _build_auth(
    es_config: ElasticsearchConfig,
) -> tuple[Any, Any, Any]:
    basic_auth = es_config.client.basic_auth
    if es_config.other_settings.username:
        basic_auth = (
            es_config.other_settings.username,
            es_config.other_settings.password or "",
        )
    return (
        es_config.client.api_key,
        basic_auth,
        es_config.client.bearer_auth,
    )


def _build_transport(
    es_config: ElasticsearchConfig,
    auth: tuple[Any, Any, Any],
) -> elasticsearch9.Elasticsearch:
    api_key, basic_auth, bearer_auth = auth
    verify_ssl_paths(
        {
            "ca_certs": es_config.client.ca_certs,
            "client_cert": es_config.client.client_cert,
            "client_key": es_config.client.client_key,
        }
    )
    hosts = list(es_config.client.hosts) if es_config.client.hosts else None
    try:
        es_kwargs: dict[str, Any] = {
            "hosts": hosts,
            "cloud_id": es_config.client.cloud_id,
            "api_key": api_key,
            "basic_auth": basic_auth,
            "bearer_auth": bearer_auth,
            "verify_certs": es_config.client.verify_certs,
            "request_timeout": es_config.client.request_timeout,
        }
        if es_config.client.ca_certs is not None:
            es_kwargs["ca_certs"] = es_config.client.ca_certs
        if es_config.client.client_cert is not None:
            es_kwargs["client_cert"] = es_config.client.client_cert
        if es_config.client.client_key is not None:
            es_kwargs["client_key"] = es_config.client.client_key
        return elasticsearch9.Elasticsearch(**es_kwargs)
    except Exception as exc:
        logger.error("Failed to connect to Elasticsearch: %s", exc)
        raise ESToolBuilderException(f"Connection failed: {exc}") from exc


def create_client(
    config: dict[str, Any] | None = None,
    configfile: str | None = None,
    autoconnect: bool = False,
) -> elasticsearch9.Elasticsearch:
    """Create an Elasticsearch client from configuration.

    This is the main entry point for creating Elasticsearch clients. It accepts
    either a configuration dictionary or a path to a YAML file.

    Args:
        config: Configuration dictionary with 'elasticsearch' key containing
            'client' and 'other_settings' subkeys. Defaults to None (uses defaults).
        configfile: Path to a YAML file with the same structure as config.
            Defaults to None.
        autoconnect: If True, connect to Elasticsearch immediately.
            Defaults to False.

    Returns:
        Elasticsearch client instance.

    Raises:
        ESToolConfigurationError: If configuration is invalid.
        ESToolBuilderException: If connection fails.

    Example:
        >>> config = {'elasticsearch': {'client': {'hosts': ['http://localhost:9200']}}}
        >>> client = create_client(config)
    """
    es_config = _build_config(config, configfile)
    auth = _build_auth(es_config)
    client = _build_transport(es_config, auth)
    if autoconnect:
        try:
            client.cluster.health()
        except Exception as exc:
            logger.error("Connection test failed: %s", exc)
            raise ESToolBuilderException(f"Connection test failed: {exc}") from exc
    return client
