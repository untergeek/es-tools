"""Tests for es_tools.client.cli (optional Click extra)."""

from __future__ import annotations

import pytest
from click.testing import CliRunner


def test_create_client_stays_click_free() -> None:
    """Library create_client must import without the cli extra."""
    from es_tools.client import create_client

    assert create_client is not None
    import es_tools.client as client_mod

    assert not hasattr(client_mod, "option_wrapper")


def test_dummy_command_help_lists_hosts() -> None:
    """OPTION_DEFAULTS + options_from_dict attach --hosts to a dummy command."""
    click = pytest.importorskip("click")
    from es_tools.client.cli import OPTION_DEFAULTS, options_from_dict

    @options_from_dict({"hosts": OPTION_DEFAULTS["hosts"]})
    @click.command()
    def dummy(hosts: tuple[str, ...]) -> None:
        click.echo(",".join(hosts) if hosts else "none")

    result = CliRunner().invoke(dummy, ["--help"])
    assert result.exit_code == 0
    assert "--hosts" in result.output


def test_option_wrapper_is_click_option() -> None:
    """option_wrapper() returns passthrough(click.option)."""
    pytest.importorskip("click")
    from es_tools.client.cli import option_wrapper

    wrap = option_wrapper()
    assert callable(wrap)


def test_get_client_uses_create_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_client must not import Builder; it calls create_client."""
    pytest.importorskip("click")
    from es_tools.client import cli as cli_mod

    seen: list[object] = []

    def fake_create(config: object) -> str:
        seen.append(config)
        return "client"

    monkeypatch.setattr(cli_mod, "create_client", fake_create)
    cfg = {"elasticsearch": {"client": {"hosts": ["http://localhost:9200"]}}}
    assert cli_mod.get_client(configdict=cfg) == "client"
    assert seen == [cfg]


def test_show_all_options_prints_help_and_exits() -> None:
    """show_all_options echoes help and exits."""
    click = pytest.importorskip("click")
    from es_tools.client.cli import SHOW_EVERYTHING, options_from_dict, show_all_options

    @options_from_dict({"hosts": SHOW_EVERYTHING["hosts"]})
    @click.command()
    @click.pass_context
    def dummy(ctx: click.Context, hosts: tuple[str, ...]) -> None:
        del hosts
        show_all_options(ctx)

    result = CliRunner().invoke(dummy, [])
    assert result.exit_code == 0
    assert "--hosts" in result.output
