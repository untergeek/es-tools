"""Configuration management for es_tools.utils.

Provides utilities for loading, saving, and managing configuration files.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manage configuration files.

    Provides methods to load, save, and manage YAML configuration files.

    Args:
        config_path: Path to configuration file.

    Example:
        >>> manager = ConfigManager("path/to/config.yml")
        >>> config = manager.load()
    """

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self._config: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        """Load configuration from file.

        Returns:
            Configuration dictionary.

        Raises:
            FileNotFoundError: If configuration file doesn't exist.
            yaml.YAMLError: If YAML is invalid.

        Example:
            >>> config = manager.load()
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path) as f:
            loaded: dict[str, Any] = yaml.safe_load(f) or {}
        self._config = loaded
        logger.debug(f"Loaded configuration from {self.config_path}")
        return loaded

    def save(self, config: dict[str, Any] | None = None) -> None:
        """Save configuration to file.

        Args:
            config: Configuration dictionary to save (default: current config).

        Raises:
            OSError: If file cannot be written.

        Example:
            >>> manager.save({"key": "value"})
        """
        if config is None:
            config = self._config

        if config is None:
            raise ValueError("No configuration to save")

        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        logger.debug(f"Saved configuration to {self.config_path}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: Configuration key.
            default: Default value if key not found.

        Returns:
            Configuration value.

        Example:
            >>> value = manager.get("key", default="default")
        """
        if self._config is None:
            self.load()
        if self._config is None:
            return default
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value.

        Args:
            key: Configuration key.
            value: Configuration value.

        Example:
            >>> manager.set("key", "value")
        """
        if self._config is None:
            self.load()
        if self._config is None:
            self._config = {}
        self._config[key] = value

    def __repr__(self) -> str:
        """Return string representation."""
        return f"ConfigManager(path={self.config_path!r})"


def load_config(path: str | Path) -> dict[str, Any]:
    """Load configuration from a file.

    Args:
        path: Path to configuration file.

    Returns:
        Configuration dictionary.

    Example:
        >>> config = load_config("path/to/config.yml")
    """
    manager = ConfigManager(path)
    return manager.load()


def save_config(path: str | Path, config: dict[str, Any]) -> None:
    """Save configuration to a file.

    Args:
        path: Path to configuration file.
        config: Configuration dictionary to save.

    Example:
        >>> save_config("path/to/config.yml", {"key": "value"})
    """
    manager = ConfigManager(path)
    manager.save(config)
