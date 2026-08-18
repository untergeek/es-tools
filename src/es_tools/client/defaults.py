"""Default configuration values for es_tools.client.

Contains constants, Click command settings, and voluptuous validation schemas.
"""

from typing import Any

# Minimum supported Elasticsearch version
VERSION_MIN: tuple[int, int, int] = (9, 0, 0)

# Maximum supported Elasticsearch version
VERSION_MAX: tuple[int, int, int] = (9, 9, 999)

# Default Elasticsearch host
ES_DEFAULT: dict[str, Any] = {
    "elasticsearch": {
        "client": {
            "hosts": ["http://127.0.0.1:9200"],
        },
        "other_settings": {},
    }
}

# Client settings keys
CLIENT_SETTINGS: list[str] = [
    "hosts",
    "cloud_id",
    "api_key",
    "basic_auth",
    "bearer_auth",
    "verify_certs",
    "ca_certs",
    "client_cert",
    "client_key",
    "request_timeout",
]

# Other settings keys
OTHER_SETTINGS: list[str] = [
    "username",
    "password",
    "master_only",
]

# Authentication arguments
AUTH_ARGS: list[str] = [
    "username",
    "password",
    "api_key",
    "basic_auth",
    "bearer_auth",
]

# SSL settings
SSL_SETTINGS: list[str] = [
    "verify_certs",
    "ca_certs",
    "client_cert",
    "client_key",
]

# Configuration arguments
CONFIG_ARGS: list[str] = [
    "configfile",
    "configdict",
]

# Hosts
HOSTS: list[str] = [
    "hosts",
]

# Cloud ID
CLOUD_ID: str = "cloud_id"

# Password
PASSWORD: str = "password"

# Username
USERNAME: str = "username"

# Keys to redact from data
KEYS_TO_REDACT: list[str] = [
    "password",
    "secret",
    "token",
    "key",
    "credential",
]


def get_default_hosts() -> list[str]:
    """Get default Elasticsearch hosts.

    Returns:
        List of default host URLs.
    """
    return ES_DEFAULT["elasticsearch"]["client"]["hosts"]


def get_client_settings() -> list[str]:
    """Get client settings keys.

    Returns:
        List of client settings keys.
    """
    return CLIENT_SETTINGS


def get_other_settings() -> list[str]:
    """Get other settings keys.

    Returns:
        List of other settings keys.
    """
    return OTHER_SETTINGS
