"""Helper utilities for es_tools.utils.

Common helper functions used across the es_tools package.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def ensure_list(value: Any) -> list[Any]:
    """Ensure a value is a list.

    Args:
        value: Value to convert to list.

    Returns:
        List containing the value.

    Example:
        >>> ensure_list("hello")
        ['hello']
        >>> ensure_list(["a", "b"])
        ['a', 'b']
        >>> ensure_list(None)
        []
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def get_version() -> str:
    """Get the es_tools version.

    Returns:
        Version string.

    Example:
        >>> get_version()
        '1.0.0'
    """
    from importlib.metadata import version

    return version("es-tools")


def log_exception(
    exc: Exception, logger: logging.Logger, level: int = logging.ERROR
) -> None:
    """Log an exception with context.

    Args:
        exc: Exception to log.
        logger: Logger instance.
        level: Log level.
    """
    logger.log(level, f"Exception: {exc.__class__.__name__}: {exc}")
    if logger.isEnabledFor(logging.DEBUG):
        import traceback

        logger.debug(traceback.format_exc())


def pluralize(word: str, count: int | None = None) -> str:
    """Pluralize a word.

    Args:
        word: Word to pluralize.
        count: Count to determine pluralization (default: None).

    Returns:
        Pluralized word.

    Example:
        >>> pluralize("index")
        'indexes'
        >>> pluralize("index", 1)
        'index'
    """
    if count is not None and count == 1:
        return word
    if word.endswith("x") or word.endswith("s"):
        return word + "es"
    if word.endswith("y"):
        return word[:-1] + "ies"
    return word + "s"


def redact(data: Any, keys_to_redact: list[str] | None = None) -> Any:
    """Redact sensitive information from data.

    Args:
        data: Data to redact.
        keys_to_redact: List of keys to redact (default: ['password', 'secret', 'token', 'key']).

    Returns:
        Redacted data.

    Example:
        >>> redact({"password": "secret", "name": "test"})
        {'password': '***', 'name': 'test'}
    """
    if keys_to_redact is None:
        keys_to_redact = ["password", "secret", "token", "key", "credential"]

    if isinstance(data, dict):
        return {
            k: "***" if k.lower() in keys_to_redact else redact(v, keys_to_redact)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [redact(item, keys_to_redact) for item in data]
    return data


def to_bool(value: Any) -> bool:
    """Convert a value to boolean.

    Args:
        value: Value to convert.

    Returns:
        Boolean value.

    Example:
        >>> to_bool("true")
        True
        >>> to_bool("0")
        False
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "yes", "1", "on")
    return bool(value)


def to_int(value: Any, default: int = 0) -> int:
    """Convert a value to integer.

    Args:
        value: Value to convert.
        default: Default value if conversion fails.

    Returns:
        Integer value.

    Example:
        >>> to_int("123")
        123
        >>> to_int("invalid", default=0)
        0
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def to_str(value: Any) -> str:
    """Convert a value to string.

    Args:
        value: Value to convert.

    Returns:
        String representation.

    Example:
        >>> to_str(123)
        '123'
        >>> to_str(None)
        ''
    """
    if value is None:
        return ""
    return str(value)
