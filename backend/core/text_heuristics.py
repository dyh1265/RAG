"""Shared text heuristics for ingest and retrieval."""

from __future__ import annotations

import re

_CODE_LINE = re.compile(r"^\s*\d+:\s*\S")
_ALGORITHM_BODY_MARKERS = (
    "__ballot",
    "__ffs",
    "end if",
    "int32",
    "for i from",
    "thread_id",
    "warp_size",
)


def looks_like_algorithm_body(text: str) -> bool:
    """True for pseudocode / numbered algorithm lines."""
    stripped = text.strip()
    if _CODE_LINE.match(stripped):
        return True
    return any(marker in stripped for marker in _ALGORITHM_BODY_MARKERS)
