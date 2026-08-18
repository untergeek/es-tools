"""Data classes for Elasticsearch client configuration.

These dataclasses provide type-safe, immutable configuration objects
that replace DotMap usage throughout the client module.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ClientConfig:
    """Client-specific configuration settings."""

    hosts: list[str] = field(default_factory=lambda: ["http://127.0.0.1:9200"])
    cloud_id: str | None = None
    api_key: str | tuple[str, str] | None = None
    basic_auth: tuple[str, str] | None = None
    bearer_auth: str | None = None
    verify_certs: bool = True
    ca_certs: str | None = None
    client_cert: str | None = None
    client_key: str | None = None
    request_timeout: float | None = None


@dataclass(frozen=True)
class OtherSettings:
    """Additional settings for Elasticsearch client."""

    username: str | None = None
    password: str | None = None
    master_only: bool = False


@dataclass(frozen=True)
class ElasticsearchConfig:
    """Complete Elasticsearch configuration."""

    client: ClientConfig = field(default_factory=ClientConfig)
    other_settings: OtherSettings = field(default_factory=OtherSettings)
