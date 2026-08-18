"""Utility functions for es_tools.redact.

Provides helper functions for redaction configuration and program lifecycle.

Example:
    >>> from es_tools.redact.helpers.utils import get_redactions
    >>> config = get_redactions("redactions.yaml")
"""

import logging
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def end_it() -> None:
    """End the program gracefully.

    Exits the current Python process with code 0.

    Example:
        >>> end_it()  # Exits immediately
    """
    import sys

    sys.exit(0)


def get_redactions(
    redaction_file: str,
    redaction_dict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load redaction configuration from file or dictionary.

    Loads redaction configuration from a YAML file or returns a provided
    dictionary. If neither is provided, returns an empty dictionary.

    Args:
        redaction_file: Path to redaction configuration file.
        redaction_dict: Redaction configuration dictionary.

    Returns:
        Redaction configuration dictionary.

    Raises:
        FileNotFoundError: If file doesn't exist.
        yaml.YAMLError: If YAML is invalid.

    Example:
        >>> config = get_redactions("redactions.yaml")
        >>> config = get_redactions(redaction_dict={"field": "value"})
    """
    if redaction_dict:
        return redaction_dict

    if redaction_file:
        with open(redaction_file) as f:
            return yaml.safe_load(f)

    return {}
