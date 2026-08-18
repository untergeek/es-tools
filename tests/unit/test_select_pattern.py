"""Tests for es_tools.select pattern selector."""

from __future__ import annotations

import pytest

from es_tools.select import PatternFilter, SelectContext, apply_filters


class _Cat:
    def __init__(self) -> None:
        self.calls: list[str | None] = []

    def indices(
        self,
        index: str | None = None,
        h: str | None = None,
        format: str | None = None,
    ) -> list[dict[str, str]]:
        self.calls.append(index)
        if index == "logs-*":
            return [{"index": "logs-000001"}, {"index": "logs-000002"}]
        if index == "*-prod":
            return [{"index": "app-prod"}, {"index": "web-prod"}]
        if index == "*":
            return [{"index": "logs-000001"}, {"index": "other"}]
        return []


class _Client:
    def __init__(self) -> None:
        self.cat = _Cat()


def test_prefix_uses_wildcard_not_star() -> None:
    client = _Client()
    ctx = SelectContext(client=client, target="index")
    names = apply_filters(
        ctx, [PatternFilter(pattern_kind="prefix", value="logs-")]
    )
    assert client.cat.calls == ["logs-*"]
    assert names == ["logs-000001", "logs-000002"]


def test_suffix_uses_wildcard() -> None:
    client = _Client()
    ctx = SelectContext(client=client, target="index")
    names = apply_filters(
        ctx, [PatternFilter(pattern_kind="suffix", value="-prod")]
    )
    assert client.cat.calls == ["*-prod"]
    assert names == ["app-prod", "web-prod"]


def test_regex_is_not_a_selector() -> None:
    ctx = SelectContext(client=object(), target="index")
    with pytest.raises(ValueError, match="regex"):
        apply_filters(ctx, [PatternFilter(pattern_kind="regex", value="logs-.*")])


def test_regex_filters_incoming_names() -> None:
    client = _Client()
    ctx = SelectContext(client=client, target="index")
    names = apply_filters(
        ctx,
        [
            PatternFilter(pattern_kind="prefix", value="logs-"),
            PatternFilter(pattern_kind="regex", value=r"000002$"),
        ],
    )
    assert names == ["logs-000002"]


def test_empty_prefix_requires_unbounded() -> None:
    ctx = SelectContext(client=object(), target="index")
    with pytest.raises(ValueError, match="allow_unbounded"):
        apply_filters(ctx, [PatternFilter(pattern_kind="prefix", value="")])


def test_empty_suffix_requires_unbounded() -> None:
    ctx = SelectContext(client=object(), target="index")
    with pytest.raises(ValueError, match="allow_unbounded"):
        apply_filters(ctx, [PatternFilter(pattern_kind="suffix", value="")])


def test_empty_prefix_allowed_when_unbounded() -> None:
    client = _Client()
    ctx = SelectContext(client=client, target="index", allow_unbounded=True)
    names = apply_filters(ctx, [PatternFilter(pattern_kind="prefix", value="")])
    assert client.cat.calls == ["*"]
    assert names == ["logs-000001", "other"]


def test_pattern_exclude_as_second() -> None:
    client = _Client()
    ctx = SelectContext(client=client, target="index")
    names = apply_filters(
        ctx,
        [
            PatternFilter(pattern_kind="prefix", value="logs-"),
            PatternFilter(pattern_kind="prefix", value="logs-000002", exclude=True),
        ],
    )
    assert names == ["logs-000001"]
