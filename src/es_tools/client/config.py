"""Configuration management for es_tools.client.

Provides Click CLI integration, option parsing, and configuration merging
using Pydantic validation models.
"""

import logging
import typing as t
from pathlib import Path
from typing import Any

from tiered_debug import TieredDebug

from es_tools.exceptions import ESToolConfigurationError

from .defaults import (
    OTHER_SETTINGS,
    SSL_SETTINGS,
)
from .utils import prune_nones
from .validators import ElasticsearchConfigModel

logger = logging.getLogger(__name__)
debug = TieredDebug(level=1, stacklevel=3)


def config_args_v2(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Process configuration arguments (v2).

    Args:
        args (dict): Parameters from :attr:`ctx.params <click.Context.params>`.
        ctx (:class:`click.Context`): Click command context.

    Returns:
        dict: Updated `args` with configuration values.
    """
    debug.lv2("Processing configuration arguments (v2)")

    # Load config file if provided
    if ctx.params.get("configfile"):
        configfile = ctx.params["configfile"]
        if not Path(configfile).is_file():
            raise ESToolConfigurationError(f"Config file not found: {configfile}")

        import yaml

        with open(configfile) as f:
            config_data = yaml.safe_load(f) or {}

        # Merge config data into args
        if "elasticsearch" in config_data:
            if "client" in config_data["elasticsearch"]:
                args.update(config_data["elasticsearch"]["client"])
            if "other_settings" in config_data["elasticsearch"]:
                args.update(config_data["elasticsearch"]["other_settings"])

    # Process CLI arguments
    for key in ctx.params:
        if key in args or key in OTHER_SETTINGS:
            args[key] = ctx.params[key]

    return prune_nones(args)


def hosts_override_v2(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Override cloud_id when hosts provided via CLI (v2 - fixed).

    Args:
        args (dict): Parameters from :attr:`ctx.params <click.Context.params>`.
        ctx (:class:`click.Context`): Click command context.

    Returns:
        dict: Updated `args` with `cloud_id` removed if `hosts` is present.

    Ensures command-line `hosts` supersedes config file `cloud_id`, as they are mutually
    exclusive. Updates :attr:`ctx.obj['client_args'] <click.Context.obj>`.

    Example:
        >>> from click import Context, Command
        >>> ctx = Context(Command('cmd'), obj={'client_args': {'cloud_id': 'my_cloud_id', 'hosts': ['http://localhost']}})
        >>> ctx.params = {'hosts': ['http://localhost'], 'configfile': None}
        >>> args = {'cloud_id': 'my_cloud_id'}
        >>> hosts_override_v2(args, ctx)
        {}

    If `hosts` are provided at the command-line and are present in
    :py:attr:`ctx.params['hosts'] <click.Context.params>`, but `cloud_id` was in the
    config file, we need to remove the `cloud_id` key from the configuration dictionary
    built from the YAML file before merging. Command-line provided arguments always
    supersede configuration file ones, including `hosts` overriding a file-based
    `cloud_id`.

    This function returns an updated dictionary `args` to be used for the final
    configuration as well as updates the :py:attr:`ctx.obj['client_args']
    <click.Context.obj>` object. It's simply easier to merge dictionaries using a
    separate object. It would be a pain and unnecessary to make another entry in
    :py:attr:`ctx.obj <click.Context.obj>` for this.
    """
    debug.lv2("Processing hosts override (v2 - fixed)")

    if ctx.params.get("hosts"):
        # Only clear cloud_id, preserve CLI hosts
        ctx.obj["client_args"].cloud_id = None
        # Remove cloud_id from args if present
        args.pop("cloud_id", None)

    return args


def password(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Process password argument.

    Args:
        args (dict): Parameters from :attr:`ctx.params <click.Context.params>`.
        ctx (:class:`click.Context`): Click command context.

    Returns:
        dict: Updated `args` with password from environment if provided.
    """
    debug.lv2("Processing password argument")

    if ctx.params.get("password"):
        args["password"] = ctx.params["password"]
    elif "ES_PASSWORD" in ctx.env_vars:
        args["password"] = ctx.env_vars["ES_PASSWORD"]

    return args


def username(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Process username argument.

    Args:
        args (dict): Parameters from :attr:`ctx.params <click.Context.params>`.
        ctx (:class:`click.Context`): Click command context.

    Returns:
        dict: Updated `args` with username from environment if provided.
    """
    debug.lv2("Processing username argument")

    if ctx.params.get("username"):
        args["username"] = ctx.params["username"]
    elif "ES_USERNAME" in ctx.env_vars:
        args["username"] = ctx.env_vars["ES_USERNAME"]

    return args


def ssl_settings(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Process SSL settings.

    Args:
        args (dict): Parameters from :attr:`ctx.params <click.Context.params>`.
        ctx (:class:`click.Context`): Click command context.

    Returns:
        dict: Updated `args` with SSL settings.
    """
    debug.lv2("Processing SSL settings")

    for key in SSL_SETTINGS:
        if ctx.params.get(key):
            args[key] = ctx.params[key]

    return args


class ConfigParser:
    """Parse and validate Elasticsearch configuration.

    Handles configuration from YAML files, dictionaries, and CLI arguments.

    Args:
        configfile (str, optional): Path to YAML configuration file.
        configdict (dict, optional): Configuration dictionary.

    Example:
        >>> parser = ConfigParser(configfile="config.yml")
        >>> config = parser.parse()
    """

    def __init__(
        self,
        configfile: str | None = None,
        configdict: dict[str, t.Any] | None = None,
    ):
        self.configfile = configfile
        self.configdict = configdict
        self.config: dict[str, t.Any] = {}

    def parse(self) -> dict[str, t.Any]:
        """Parse configuration from file or dictionary.

        Returns:
            dict: Parsed configuration dictionary.

        Raises:
            ESToolConfigurationError: If configuration is invalid.
        """
        debug.lv2("Parsing configuration")

        if self.configfile:
            import yaml

            if not Path(self.configfile).is_file():
                raise ESToolConfigurationError(
                    f"Config file not found: {self.configfile}"
                )

            with open(self.configfile) as f:
                self.config = yaml.safe_load(f) or {}

        elif self.configdict:
            self.config = self.configdict

        else:
            # Use defaults
            from .defaults import ES_DEFAULT

            self.config = ES_DEFAULT

        # Validate using Pydantic
        self._validate()

        debug.lv3(f"Parsed configuration: {self.config}")
        return self.config

    def _validate(self) -> None:
        """Validate configuration using Pydantic models.

        Raises:
            ESToolConfigurationError: If configuration is invalid.
        """
        if not self.config:
            raise ESToolConfigurationError("Configuration is empty")

        if "elasticsearch" not in self.config:
            raise ESToolConfigurationError(
                "Configuration must contain 'elasticsearch' key"
            )

        if "client" not in self.config["elasticsearch"]:
            raise ESToolConfigurationError(
                "Configuration must contain 'elasticsearch.client' key"
            )

        # Use Pydantic for comprehensive validation
        try:
            ElasticsearchConfigModel.model_validate(self.config["elasticsearch"])
        except Exception as e:
            raise ESToolConfigurationError(str(e)) from e

    def __repr__(self) -> str:
        """Return string representation."""
        return f"ConfigParser(file={self.configfile!r}, dict={self.configdict is not None})"
