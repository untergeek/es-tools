"""Split Elasticsearch name lists so URI-bound APIs stay under the URL size limit."""

from __future__ import annotations


def chunk_names(names: list[str], max_bytes: int = 3072) -> list[list[str]]:
    """Split names so ``','.join(chunk)`` stays at or under ``max_bytes``.

    Used only for APIs that put the name list in the request URI (open, close,
    delete, put_settings). Body APIs such as snapshot/restore must not use this.

    A single name longer than ``max_bytes`` is still emitted as its own chunk.

    Args:
        names: Index or snapshot names.
        max_bytes: Maximum length of the comma-joined CSV (default 3072).

    Returns:
        A list of name chunks. An empty input yields an empty list.

    Example:
        >>> chunk_names(["a", "b"])
        [['a', 'b']]
        >>> chunk_names([])
        []
    """
    if not names:
        return []

    chunks: list[list[str]] = []
    current: list[str] = []
    current_len = 0
    for name in names:
        added = len(name) if not current else len(name) + 1
        if current and current_len + added > max_bytes:
            chunks.append(current)
            current = [name]
            current_len = len(name)
        else:
            current.append(name)
            current_len += added
    if current:
        chunks.append(current)
    return chunks
