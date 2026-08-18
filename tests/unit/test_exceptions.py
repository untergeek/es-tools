"""Exception hierarchy tests."""

from __future__ import annotations

from es_tools.exceptions import ESToolActionError, ESToolException


def test_action_error_is_shared() -> None:
    """ESToolActionError is a shared list-action error."""
    assert issubclass(ESToolActionError, ESToolException)
