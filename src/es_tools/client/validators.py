"""Pydantic validation models for Elasticsearch configuration.

These models provide comprehensive validation and type coercion for configuration
dictionaries, making them reusable across es_tools submodules.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class ClientConfigModel(BaseModel):
    """Pydantic model for client configuration with validation."""

    hosts: list[str] | None = None
    cloud_id: str | None = None
    api_key: str | tuple[str, str] | None = None
    basic_auth: tuple[str, str] | None = None
    bearer_auth: str | None = None
    verify_certs: bool = True
    ca_certs: str | None = None
    client_cert: str | None = None
    client_key: str | None = None
    request_timeout: float | None = None

    @field_validator("hosts")
    @classmethod
    def validate_hosts(cls, v: list[str] | None) -> list[str] | None:
        """Validate hosts list.

        ``None`` means unset (caller may fill a default later). An explicit
        empty list is invalid.

        Args:
            v: Host URLs, or ``None`` if the caller omitted hosts.

        Returns:
            The hosts list, or ``None`` if unset.

        Raises:
            ValueError: If ``v`` is an empty list.
        """
        if v is None:
            return None
        if not v:
            raise ValueError("hosts cannot be empty")
        return v

    @field_validator("api_key", mode="before")
    @classmethod
    def validate_api_key(cls, v: object) -> str | tuple[str, str] | None:
        """Accept ES9 str or (id, key); coerce a two-item list."""
        if v is None:
            return None
        if isinstance(v, str):
            if not v:
                raise ValueError("api_key cannot be empty")
            return v
        if isinstance(v, (list, tuple)):
            if len(v) != 2 or not all(isinstance(x, str) and x for x in v):
                raise ValueError(
                    "api_key tuple must be two non-empty strings (id, key)"
                )
            return (v[0], v[1])
        raise ValueError("api_key must be a string or (id, key) tuple")

    @model_validator(mode="after")
    def check_hosts_cloud_id_conflict(self) -> ClientConfigModel:
        """Ensure hosts and cloud_id are not both set."""
        if self.hosts and self.cloud_id:
            raise ValueError("Cannot specify both 'hosts' and 'cloud_id'")
        return self


class OtherSettingsModel(BaseModel):
    """Pydantic model for additional settings."""

    username: str | None = None
    password: str | None = None
    master_only: bool = False

    @model_validator(mode="after")
    def validate_master_only_hosts(self) -> OtherSettingsModel:
        """Validate master_only constraint."""
        # This will be validated at the parent level with hosts info
        return self


class ElasticsearchConfigModel(BaseModel):
    """Pydantic model for complete Elasticsearch configuration."""

    client: ClientConfigModel
    other_settings: OtherSettingsModel = Field(default_factory=OtherSettingsModel)

    @model_validator(mode="after")
    def validate_master_only_with_single_host(self) -> ElasticsearchConfigModel:
        """Validate master_only requires single host."""
        if self.other_settings.master_only and len(self.client.hosts or []) > 1:
            raise ValueError(
                f"master_only cannot be True with multiple hosts: {self.client.hosts}"
            )
        return self
