"""Parse and match table/figure/algorithm labels in queries."""

from __future__ import annotations

import re
from typing import Literal

from backend.core.text_heuristics import looks_like_algorithm_body

AssetKind = Literal["table", "figure", "algorithm"]

_ASSET_REF = re.compile(
    r"\b(table|figure|fig\.?|algorithm|alg\.?)\s*([0-9]+|[ivxlcdm]+)\b",
    re.IGNORECASE,
)

# "page 7", "slide 12", "pg. 3", "slide #4" — used to scope a query to a single
# lecture slide / document page. Plural forms ("pages 7") deliberately do not match.
_PAGE_REF = re.compile(
    r"\b(?:slide|page|pg)\.?\s*#?\s*([0-9]{1,4})\b",
    re.IGNORECASE,
)

# Common IEEE / academic Roman numerals.
_ROMAN_BY_DIGIT: dict[int, str] = {
    1: "I",
    2: "II",
    3: "III",
    4: "IV",
    5: "V",
    6: "VI",
    7: "VII",
    8: "VIII",
    9: "IX",
    10: "X",
    11: "XI",
    12: "XII",
    13: "XIII",
    14: "XIV",
    15: "XV",
}

__all__ = [
    "AssetKind",
    "content_matches_asset_label",
    "looks_like_algorithm_body",
    "normalize_reference_keywords",
    "parse_asset_reference",
    "parse_page_reference",
]

# Common misspellings of structural reference keywords. Normalized before
# reference detection so typos like "slde 7" still trigger scoped retrieval.
# Canonical spellings are intentionally excluded (they already match).
_REFERENCE_TYPOS: dict[str, tuple[str, ...]] = {
    "slide": ("slde", "silde", "sldie", "slied"),
    "page": ("pge", "paeg", "paje"),
    "figure": ("figuer", "figue", "figur", "fgure", "fiugre"),
    "table": ("tabel", "tble", "talbe"),
    "algorithm": ("algorith", "algorthm", "algoritm", "algorihm", "algorithim"),
}

# Each typo only normalizes when immediately followed by a number (optionally a
# '#'), e.g. "slde 7" / "figuer2" — so ordinary prose is never rewritten.
_TYPO_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (
        canonical,
        re.compile(
            r"\b(?:" + "|".join(variants) + r")(?=\s*#?\s*[0-9])",
            re.IGNORECASE,
        ),
    )
    for canonical, variants in _REFERENCE_TYPOS.items()
)


def normalize_reference_keywords(text: str) -> str:
    """Fix common misspellings of slide/page/figure/table/algorithm before reference parsing.

    Only rewrites a typo that is immediately followed by a number (e.g. ``"slde 7"`` →
    ``"slide 7"``), leaving ordinary prose untouched. Used solely for structural
    reference detection; the original query is still embedded and shown to the user/LLM.
    """
    result = text
    for canonical, pattern in _TYPO_PATTERNS:
        result = pattern.sub(canonical, result)
    return result


def parse_asset_reference(query: str) -> tuple[AssetKind, str] | None:
    """Return (kind, number_token) when the query names a table, figure, or algorithm."""
    match = _ASSET_REF.search(normalize_reference_keywords(query.strip()))
    if not match:
        return None
    raw_kind = match.group(1).lower().rstrip(".")
    if raw_kind.startswith("fig"):
        kind: AssetKind = "figure"
    elif raw_kind.startswith("alg"):
        kind = "algorithm"
    else:
        kind = "table" if raw_kind == "table" else "figure"
    number = match.group(2)
    return kind, number


def parse_page_reference(query: str) -> int | None:
    """Return the 1-indexed page/slide number when a query names ``page N`` / ``slide N``."""
    match = _PAGE_REF.search(normalize_reference_keywords(query.strip()))
    if not match:
        return None
    try:
        number = int(match.group(1))
    except ValueError:
        return None
    return number if number > 0 else None


def _label_variants(kind: AssetKind, number: str) -> list[str]:
    """Alternate spellings to match in chunk text (Arabic vs Roman)."""
    number = number.strip()
    variants: list[str] = []
    if kind == "table":
        variants.extend((f"table {number}", f"Table {number}", f"TABLE {number}"))
        if number.isdigit():
            roman = _ROMAN_BY_DIGIT.get(int(number))
            if roman:
                variants.extend((f"Table {roman}", f"table {roman}", f"TABLE {roman}"))
    elif kind == "figure":
        variants.extend(
            (
                f"figure {number}",
                f"Figure {number}",
                f"FIGURE {number}",
                f"fig. {number}",
                f"Fig. {number}",
            )
        )
        if number.isdigit():
            roman = _ROMAN_BY_DIGIT.get(int(number))
            if roman:
                variants.extend((f"Figure {roman}", f"figure {roman}", f"Fig. {roman}"))
    else:
        variants.extend(
            (
                f"algorithm {number}",
                f"Algorithm {number}",
                f"ALGORITHM {number}",
                f"alg. {number}",
                f"Alg. {number}",
            )
        )
        if number.isdigit():
            roman = _ROMAN_BY_DIGIT.get(int(number))
            if roman:
                variants.extend(
                    (f"Algorithm {roman}", f"algorithm {roman}", f"Alg. {roman}")
                )
    return variants


def content_matches_asset_label(content: str, kind: AssetKind, number: str) -> bool:
    """True when chunk text likely describes the requested labeled asset."""
    lowered = content.lower()
    for label in _label_variants(kind, number):
        if label.lower() in lowered:
            return True
    return False
