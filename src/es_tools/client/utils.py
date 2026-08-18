"""Helper utilities for es_tools.client.

Provides common helper functions used across the client module.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from es_tools.exceptions import ESToolVersionError
from es_tools.utils.helpers import ensure_list as ensure_list

from .defaults import VERSION_MAX, VERSION_MIN

logger = logging.getLogger(__name__)


def get_version(client: Any) -> tuple[int, int, int]:
    """Return the cluster version as ``(major, minor, patch)``.

    Args:
        client: Elasticsearch client.

    Returns:
        Three-int version tuple.

    Raises:
        ESToolVersionError: If ``info()`` fails or the number is unparsable.
    """
    try:
        info = client.info()
        raw = info.get("version", {}).get("number", "")
        core = str(raw).split("-", 1)[0]
        parts = core.split(".")
        nums = [int(p) for p in parts[:3]]
    except Exception as exc:
        raise ESToolVersionError(f"Failed to get version: {exc}") from exc
    if len(nums) < 3:
        nums.extend([0] * (3 - len(nums)))
    if not nums:
        raise ESToolVersionError("Failed to get version: empty number")
    return (nums[0], nums[1], nums[2])


def check_es_version(
    client: Any,
    *,
    version_min: tuple[int, int, int] = VERSION_MIN,
    version_max: tuple[int, int, int] | None = VERSION_MAX,
) -> tuple[int, int, int]:
    """Raise if the cluster version is outside ``[version_min, version_max]``.

    ``create_client`` does not call this. Pass ``version_max=None`` for no
    ceiling. Callers that need 8.x skip this helper or pass their own bounds.

    Args:
        client: Elasticsearch client.
        version_min: Inclusive lower bound. Defaults to ``VERSION_MIN``.
        version_max: Inclusive upper bound, or ``None`` for no max.
            Defaults to ``VERSION_MAX``.

    Returns:
        The running ``(major, minor, patch)``.

    Raises:
        ESToolVersionError: If ``info()`` fails or the version is out of range.
    """
    running = get_version(client)
    if running < version_min:
        raise ESToolVersionError(
            f"Elasticsearch {running} is below minimum {version_min}"
        )
    if version_max is not None and running > version_max:
        raise ESToolVersionError(
            f"Elasticsearch {running} is above maximum {version_max}"
        )
    return running


def get_yaml(filepath: str) -> dict[str, Any]:
    """Load YAML file.

    Args:
        filepath: Path to YAML file.

    Returns:
        Parsed YAML dictionary.

    Raises:
        FileNotFoundError: If file doesn't exist.
        yaml.YAMLError: If YAML is invalid.

    Example:
        >>> # Mock usage
        >>> get_yaml("/nonexistent.yaml")  # doctest: +SKIP
    """
    if not Path(filepath).is_file():
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(filepath) as f:
        loaded = yaml.safe_load(f)
        return loaded if isinstance(loaded, dict) else {}


def parse_apikey_token(token: str) -> tuple[str, str]:
    """Parse API key token into id and key.

    Args:
        token: Base64-encoded API key token.

    Returns:
        Tuple of (id, key).

    Raises:
        ValueError: If token is invalid.

    Example:
        >>> # Mock usage
        >>> parse_apikey_token("invalid")  # doctest: +SKIP
    """
    import base64
    import json

    try:
        decoded = base64.b64decode(token).decode("utf-8")
        data = json.loads(decoded)
        return data["id"], data["api_key"]
    except Exception as e:
        raise ValueError(f"Invalid API key token: {e}") from e


def prune_nones(config: dict[str, Any]) -> dict[str, Any]:
    """Remove None values from configuration dictionary.

    Args:
        config: Configuration dictionary.

    Returns:
        Dictionary with None values removed.

    Example:
        >>> prune_nones({"a": 1, "b": None, "c": "test"})
        {'a': 1, 'c': 'test'}
    """

    def prune(d: dict[str, Any]) -> dict[str, Any]:
        return {
            k: prune(v) if isinstance(v, dict) else v
            for k, v in d.items()
            if v is not None
        }

    return prune(config)


_SSL_PATH_KEYS = ("ca_certs", "client_cert", "client_key")


def verify_ssl_paths(args: dict[str, Any]) -> None:
    """Verify SSL certificate and key paths exist as files.

    Args:
        args: Mapping that may contain ``ca_certs``, ``client_cert``,
            and/or ``client_key``.

    Raises:
        ESToolConfigurationError: If a provided path is not a readable file.
    """
    from pathlib import Path

    from es_tools.exceptions import ESToolConfigurationError

    for key in _SSL_PATH_KEYS:
        path = args.get(key)
        if path is None:
            continue
        if not Path(path).is_file():
            raise ESToolConfigurationError(f"{key} is not a readable file: {path}")


def verify_url_schema(url: str, preserve_path: bool = False) -> str:
    """Verify URL schema is valid for Elasticsearch.

    Args:
        url: URL to verify.
        preserve_path: If True, preserve URL path (default: False).

    Returns:
        Validated URL.

    Raises:
        ConfigurationError: If schema is invalid.

    .. versionchanged:: 9.2.0
        Added ``preserve_path`` parameter to support URL paths.

    Example:
        >>> verify_url_schema("http://localhost:9200")
        'http://localhost:9200'
        >>> verify_url_schema("http://localhost:9200/some/path", preserve_path=True)
        'http://localhost:9200/some/path'
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL schema: {parsed.scheme}")

    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")

    # Reconstruct URL with proper port
    port = parsed.port or (443 if parsed.scheme == "https" else 9200)
    retval = f"{parsed.scheme}://{parsed.hostname}:{port}"

    # Preserve path if requested
    if preserve_path and parsed.path:
        retval += parsed.path

    return retval


def check_config(config: dict[str, Any]) -> dict[str, Any]:
    """Check and validate configuration dictionary.

    Args:
        config: Configuration dictionary to validate.

    Returns:
        Validated configuration dictionary.

    Raises:
        ConfigurationError: If configuration is invalid.

    Example:
        >>> check_config({'elasticsearch': {'client': {'hosts': ['http://localhost:9200']}}})
        {'elasticsearch': {'client': {'hosts': ['http://localhost:9200']}}}
    """
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a dictionary")

    if "elasticsearch" not in config:
        raise ValueError("Configuration must contain 'elasticsearch' key")

    if "client" not in config["elasticsearch"]:
        raise ValueError("Configuration must contain 'elasticsearch.client' key")

    return config
