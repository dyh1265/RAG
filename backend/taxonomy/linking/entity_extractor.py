"""Extract classification-related terms from query and answer text."""

from __future__ import annotations

import re

_CLASSIFY_AS_RE = re.compile(
    r"(?:classify(?:\s+this|\s+the\s+document)?\s+as|classification\s*[:\-]\s*|marked\s+as)\s*"
    r"([A-Za-z][A-Za-z0-9\-\s]{1,40})",
    re.IGNORECASE,
)
# Known labels longest-first so SECRET-TOP-SECRET wins over SECRET
_KNOWN_KEYWORDS = sorted(
    (
        "SECRET-TOP-SECRET",
        "TOP SECRET SCI",
        "TOP SECRET",
        "TOP-SECRET",
        "CONFIDENTIAL",
        "UNCLASSIFIED",
        "INTERNAL",
        "RESTRICTED",
        "PUBLIC",
        "SECRET",
    ),
    key=len,
    reverse=True,
)
_STOP_WORDS = (" because ", " since ", " as it ", " — ")
# Figure / visualization colors — not document classification labels
_NON_CLASSIFICATION_TERMS = frozenset({
    "GRAY", "GREY", "GREEN", "BLUE", "RED", "YELLOW", "ORANGE", "PURPLE", "BLACK", "WHITE",
})


def _normalize(term: str) -> str:
    cleaned = term.strip().strip(".,;:")
    cleaned = " ".join(cleaned.upper().replace("_", " ").replace("-", " ").split())
    lower = cleaned.lower()
    for stop in _STOP_WORDS:
        idx = lower.find(stop)
        if idx > 0:
            cleaned = cleaned[:idx].strip()
            lower = cleaned.lower()
    return cleaned


def _prune_substrings(terms: list[str]) -> list[str]:
    """Drop SECRET when SECRET TOP SECRET is already present."""
    kept: list[str] = []
    for term in sorted(terms, key=len, reverse=True):
        if any(term != other and term in other for other in kept):
            continue
        kept.append(term)
    return sorted(kept)


def extract_classification_terms(*texts: str) -> list[str]:
    """Return deduplicated classification-like terms from one or more strings."""
    found: set[str] = set()

    for text in texts:
        if not text.strip():
            continue
        for match in _CLASSIFY_AS_RE.finditer(text):
            raw = match.group(1).split(",")[0].split(";")[0]
            term = _normalize(raw)
            if term and term not in _NON_CLASSIFICATION_TERMS:
                found.add(term)
        normalized_text = _normalize(text)
        for kw in _KNOWN_KEYWORDS:
            kw_norm = _normalize(kw)
            if kw_norm in normalized_text:
                found.add(kw_norm)

    return _prune_substrings(sorted(t for t in found if t not in _NON_CLASSIFICATION_TERMS))
