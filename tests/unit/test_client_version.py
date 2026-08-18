"""Tests for client version helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from es_tools.client.utils import check_es_version, get_version
from es_tools.exceptions import ESToolVersionError


def test_get_version_parses_triple() -> None:
    client = MagicMock()
    client.info.return_value = {"version": {"number": "9.5.0"}}
    assert get_version(client) == (9, 5, 0)


def test_get_version_strips_prerelease() -> None:
    client = MagicMock()
    client.info.return_value = {"version": {"number": "9.5.0-SNAPSHOT"}}
    assert get_version(client) == (9, 5, 0)


def test_get_version_pads_short_number() -> None:
    client = MagicMock()
    client.info.return_value = {"version": {"number": "9.5"}}
    assert get_version(client) == (9, 5, 0)


def test_get_version_info_failure_is_version_error() -> None:
    client = MagicMock()
    client.info.side_effect = RuntimeError("down")
    with pytest.raises(ESToolVersionError, match="Failed to get version"):
        get_version(client)


def _client_at(number: str) -> MagicMock:
    client = MagicMock()
    client.info.return_value = {"version": {"number": number}}
    return client


def test_check_es_version_in_range_returns_triple() -> None:
    assert check_es_version(_client_at("9.5.0")) == (9, 5, 0)


def test_check_es_version_below_min_raises() -> None:
    with pytest.raises(ESToolVersionError, match="below"):
        check_es_version(_client_at("8.17.0"))


def test_check_es_version_above_max_raises() -> None:
    with pytest.raises(ESToolVersionError, match="above"):
        check_es_version(_client_at("10.0.0"))


def test_check_es_version_max_none_allows_above_default_max() -> None:
    assert check_es_version(_client_at("10.0.0"), version_max=None) == (10, 0, 0)


def test_check_es_version_custom_min() -> None:
    with pytest.raises(ESToolVersionError, match="below"):
        check_es_version(_client_at("9.5.0"), version_min=(9, 6, 0))
