"""Tests for URI name chunking."""

from es_tools.utils.chunk import chunk_names


def test_empty_list_returns_empty() -> None:
    """Empty input produces no chunks."""
    assert chunk_names([]) == []


def test_small_list_is_one_chunk() -> None:
    """A short list stays in a single chunk."""
    assert chunk_names(["a", "b"]) == [["a", "b"]]


def test_splits_when_csv_would_exceed_3072() -> None:
    """Chunks stay at or under 3072 bytes and preserve order."""
    names = [f"index-{i:04d}-{'x' * 50}" for i in range(80)]
    chunks = chunk_names(names, max_bytes=3072)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(",".join(chunk)) <= 3072
    assert [n for c in chunks for n in c] == names
