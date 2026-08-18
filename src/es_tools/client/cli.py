"""Optional Click CLI kit, ported from es_client HEAD.

Install ``es-tools[cli]``. ``create_client`` stays click-free; this module
is imported only by Click apps (Steward, Curator-style CLIs).
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import click
from click import Choice, Path

from es_tools.client.builder import create_client
from es_tools.exceptions import ESToolConfigurationError

CLICK_SETTINGS: dict[str, dict[str, Any]] = {
    "config": {"help": "Path to configuration file.", "type": Path(exists=True)},
    "hosts": {"help": "Elasticsearch URL to connect to.", "multiple": True},
    "cloud_id": {"help": "Elastic Cloud instance id"},
    "api_token": {"help": "The base64 encoded API Key token", "type": str},
    "id": {"help": 'API Key "id" value', "type": str},
    "api_key": {"help": 'API Key "api_key" value', "type": str},
    "username": {"help": "Elasticsearch username", "type": str},
    "password": {"help": "Elasticsearch password", "type": str},
    "bearer_auth": {"help": "Bearer authentication token", "type": str, "hidden": True},
    "opaque_id": {"help": "X-Opaque-Id HTTP header value", "type": str, "hidden": True},
    "request_timeout": {"help": "Request timeout in seconds", "type": float},
    "http_compress": {
        "help": "Enable HTTP compression",
        "default": None,
        "hidden": True,
    },
    "verify_certs": {"help": "Verify SSL/TLS certificate(s)", "default": None},
    "ca_certs": {"help": "Path to CA certificate file or directory", "type": str},
    "client_cert": {"help": "Path to client certificate file", "type": str},
    "client_key": {"help": "Path to client key file", "type": str},
    "ssl_assert_hostname": {
        "help": "Hostname or IP address to verify on the node's certificate.",
        "type": str,
        "hidden": True,
    },
    "ssl_assert_fingerprint": {
        "help": (
            "SHA-256 fingerprint of the node's certificate. If this value is given "
            "then root-of-trust verification isn't done and only the node's "
            "certificate fingerprint is verified."
        ),
        "type": str,
        "hidden": True,
    },
    "ssl_version": {
        "help": "Minimum acceptable TLS/SSL version",
        "type": str,
        "hidden": True,
    },
    "master-only": {
        "help": "Only run if the single host provided is the elected master",
        "default": None,
        "hidden": True,
    },
    "skip_version_test": {
        "help": "Elasticsearch version compatibility check",
        "default": None,
        "hidden": True,
    },
}

LOGGING_SETTINGS: dict[str, dict[str, Any]] = {
    "loglevel": {
        "help": "Log level",
        "type": Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
        "default": None,
    },
    "logfile": {"help": "Log file", "type": str},
    "logformat": {
        "help": "Log output format",
        "type": Choice(["default", "json", "ecs"]),
        "default": None,
    },
    "blacklist": {
        "help": "Named entities will not be logged",
        "multiple": True,
        "default": None,
        "hidden": True,
    },
}

SHOW_OPTION: dict[str, bool] = {"hidden": False}
SHOW_ENVVAR: dict[str, bool] = {"show_envvar": True}
OVERRIDE: dict[str, bool] = {**SHOW_OPTION, **SHOW_ENVVAR}
ONOFF: dict[str, str] = {"on": "", "off": "no-"}

OPTION_DEFAULTS: dict[str, dict[str, Any]] = {
    "config": {},
    "hosts": {},
    "cloud_id": {},
    "api_token": {},
    "id": {},
    "api_key": {},
    "username": {},
    "password": {},
    "bearer_auth": {},
    "opaque_id": {},
    "request_timeout": {},
    "http_compress": {"onoff": ONOFF},
    "verify_certs": {"onoff": ONOFF},
    "ca_certs": {},
    "client_cert": {},
    "client_key": {},
    "ssl_assert_hostname": {},
    "ssl_assert_fingerprint": {},
    "ssl_version": {},
    "master-only": {"onoff": ONOFF},
    "skip_version_test": {"onoff": ONOFF},
    "loglevel": {"settings": LOGGING_SETTINGS["loglevel"]},
    "logfile": {"settings": LOGGING_SETTINGS["logfile"]},
    "logformat": {"settings": LOGGING_SETTINGS["logformat"]},
    "blacklist": {"settings": LOGGING_SETTINGS["blacklist"]},
}


def all_on() -> dict[str, dict[str, Any]]:
    """Return default options with hidden flags shown."""
    options = deepcopy(OPTION_DEFAULTS)
    retval: dict[str, dict[str, Any]] = {}
    for option, spec in options.items():
        spec["override"] = dict(OVERRIDE)
        retval[option] = spec
    return retval


SHOW_EVERYTHING: dict[str, dict[str, Any]] = all_on()


def passthrough(func: Callable[..., Any]) -> Callable[..., Any]:
    """Generic wrapper for click decorators."""
    return lambda a, k: func(*a, **k)


def option_wrapper() -> Callable[..., Any]:
    """Wrap ``click.option`` for configuration storage."""
    return passthrough(click.option)


def override_settings(settings: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge override keys into ``settings`` (mutates ``settings``)."""
    if not isinstance(override, dict):
        raise ESToolConfigurationError(
            f"override must be of type dict: {type(override)}"
        )
    for key, val in override.items():
        settings[key] = val
    return settings


def cli_opts(
    value: str,
    settings: dict[str, Any] | None = None,
    onoff: dict[str, str] | None = None,
    override: dict[str, Any] | None = None,
) -> tuple[tuple[str, ...], dict[str, Any]]:
    """Build ``click.option`` decls from ``CLICK_SETTINGS``."""
    if override is None:
        override = {}
    if settings is None:
        settings = CLICK_SETTINGS
    if not isinstance(settings, dict):
        raise ESToolConfigurationError(
            f'"settings" is not a dictionary: {type(settings)}'
        )
    if value not in settings:
        raise ESToolConfigurationError(f'"{value}" not in settings')
    argval = f"--{value}"
    if isinstance(onoff, dict):
        try:
            argval = f"--{onoff['on']}{value}/--{onoff['off']}{value}"
        except KeyError as exc:
            raise ESToolConfigurationError(
                f"Unable to parse --on/--off option: {exc}"
            ) from exc
    return (argval,), override_settings(dict(settings[value]), override)


def options_from_dict(options_dict: dict[str, dict[str, Any]]) -> Callable[..., Any]:
    """Decorator to add CLI options from ``OPTION_DEFAULTS`` / ``SHOW_EVERYTHING``."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        for option in reversed(list(options_dict)):
            dct = options_dict[option]
            onoff = dct.get("onoff")
            override = dct.get("override")
            settings = dct.get("settings")
            if settings is None:
                settings = CLICK_SETTINGS[option]
            argval = f"--{option}"
            if isinstance(onoff, dict):
                argval = f"--{onoff['on']}{option}/--{onoff['off']}{option}"
            param_decls = (argval, option.replace("-", "_"))
            attrs = override_settings(dict(settings), override) if override else settings
            click.option(*param_decls, **attrs)(func)
        return func

    return decorator


def show_all_options(*_args: Any, **_kwargs: Any) -> None:
    """Echo the current command help and exit."""
    ctx = click.get_current_context()
    click.echo(ctx.get_help())
    ctx.exit()


def get_client(
    configdict: dict[str, Any] | None = None,
    configfile: str | None = None,
) -> Any:
    """Build a client via ``create_client`` (not Builder).

    ``configdict`` wins over ``configfile``. Neither → default localhost.
    """
    if configdict is None:
        if configfile:
            from es_tools.client.utils import get_yaml

            configdict = get_yaml(configfile)
        else:
            configdict = {
                "elasticsearch": {"client": {"hosts": ["http://127.0.0.1:9200"]}}
            }
    return create_client(configdict)


def configure_logging(ctx: click.Context) -> None:
    """Apply loglevel from Click params (full ecs/json formatters are later)."""
    import logging
    import sys

    level_name = (ctx.params or {}).get("loglevel") or "INFO"
    if isinstance(level_name, str):
        logging.basicConfig(
            level=getattr(logging, level_name.upper(), logging.INFO),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stderr)],
        )
