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
    "parse_asset_reference",
]


def parse_asset_reference(query: str) -> tuple[AssetKind, str] | None:
    """Return (kind, number_token) when the query names a table, figure, or algorithm."""
    match = _ASSET_REF.search(query.strip())
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
