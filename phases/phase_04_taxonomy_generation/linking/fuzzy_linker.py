"""Fuzzy-link extracted terms to taxonomy labels via rapidfuzz."""

from __future__ import annotations

from dataclasses import dataclass

from phases.phase_04_taxonomy_generation.ontology.loader import Taxonomy


@dataclass
class LinkedTerm:
    term: str
    matched_label: str | None
    score: float
    is_forbidden: bool


def _normalize(s: str) -> str:
    return " ".join(s.upper().replace("-", " ").replace("_", " ").split())


def _best_forbidden_match(norm: str, forbidden_labels: list[str]) -> str | None:
    """Return the most specific forbidden ontology label matching norm."""
    if not norm:
        return None

    by_specificity = sorted(forbidden_labels, key=lambda label: len(_normalize(label)), reverse=True)
    for forbidden in by_specificity:
        if _normalize(forbidden) == norm:
            return forbidden

    best: str | None = None
    best_len = 0
    for forbidden in by_specificity:
        f_norm = _normalize(forbidden)
        if f_norm in norm or norm in f_norm:
            if len(f_norm) > best_len:
                best = forbidden
                best_len = len(f_norm)
    return best


def link_terms(terms: list[str], taxonomy: Taxonomy, *, threshold: float = 85.0) -> list[LinkedTerm]:
    """Map each term to the best allowed/forbidden label match."""
    try:
        from rapidfuzz import fuzz, process
    except ImportError as exc:
        raise ImportError("Install rapidfuzz: pip install -e '.[phase4]'") from exc

    candidates = taxonomy.allowed_labels + taxonomy.forbidden_labels
    linked: list[LinkedTerm] = []

    for term in terms:
        norm = _normalize(term)
        if not norm:
            continue

        # Exact forbidden hit (longest / most specific label wins)
        forbidden = _best_forbidden_match(norm, taxonomy.forbidden_labels)
        if forbidden:
            linked.append(LinkedTerm(term=term, matched_label=forbidden, score=100.0, is_forbidden=True))
            continue

        match = process.extractOne(norm, [_normalize(c) for c in candidates], scorer=fuzz.token_sort_ratio)
        if match and match[1] >= threshold:
            idx = match[2]
            label = candidates[idx]
            linked.append(
                LinkedTerm(
                    term=term,
                    matched_label=label,
                    score=float(match[1]),
                    is_forbidden=label in taxonomy.forbidden_labels,
                )
            )
        else:
            linked.append(LinkedTerm(term=term, matched_label=None, score=0.0, is_forbidden=False))

    return linked
