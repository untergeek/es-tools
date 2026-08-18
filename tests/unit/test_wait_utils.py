"""Tests for es_tools.wait.utils."""

from __future__ import annotations

from types import SimpleNamespace

from es_tools.wait.utils import response_dict


def test_response_dict_plain_dict() -> None:
    """A dict is copied with string keys."""
    assert response_dict({"a": 1}) == {"a": 1}


def test_response_dict_stringifies_keys() -> None:
    """Non-str keys are passed through str()."""
    assert response_dict({1: "x"}) == {"1": "x"}


def test_response_dict_object_body() -> None:
    """ES client responses expose a dict on .body."""
    raw = SimpleNamespace(body={"ok": True})
    assert response_dict(raw) == {"ok": True}


def test_response_dict_missing_or_non_dict() -> None:
    """Anything else is an empty dict."""
    assert response_dict(None) == {}
    assert response_dict("x") == {}
    assert response_dict(SimpleNamespace()) == {}
    assert response_dict(SimpleNamespace(body="nope")) == {}
