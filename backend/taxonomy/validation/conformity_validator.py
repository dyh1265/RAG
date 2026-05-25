"""ConformityValidator — score answers against taxonomy labels."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from backend.taxonomy.linking.entity_extractor import extract_classification_terms
from backend.taxonomy.linking.fuzzy_linker import link_terms
from backend.taxonomy.ontology.loader import Taxonomy, load_taxonomy
from backend.core.config import get_settings

_NEGATION_HINTS = ("cannot", "can't", "will not", "must not", "do not", "does not", "not classify", "unable to")


def _label_norm(label: str) -> str:
    return " ".join(label.upper().replace("-", " ").split())


def _collapse_forbidden_labels(labels: list[str]) -> list[str]:
    """Drop shorter labels subsumed by a longer forbidden label in the same set."""
    unique = sorted(set(labels), key=lambda label: len(_label_norm(label)), reverse=True)
    kept: list[str] = []
    for label in unique:
        norm = _label_norm(label)
        if any(norm != _label_norm(other) and norm in _label_norm(other) for other in kept):
            continue
        kept.append(label)
    return sorted(kept)


def _forbidden_from_linked(linked: list) -> list[str]:
    labels = [lt.matched_label for lt in linked if lt.is_forbidden and lt.matched_label]
    return _collapse_forbidden_labels(labels)


def _is_negated_mention(text: str, term: str, *, canonical: str | None = None) -> bool:
    """True when term appears in a refusal/negation context."""
    upper = text.upper()
    for candidate in (canonical, term):
        if not candidate:
            continue
        t = candidate.upper().replace("-", " ")
        idx = upper.find(t.replace(" ", "-"))
        if idx < 0:
            idx = upper.find(t)
        if idx < 0:
            continue
        window = text[max(0, idx - 50) : idx].lower()
        if any(h in window for h in _NEGATION_HINTS):
            return True
    return False


@dataclass
class ConformityResult:
    score: float
    flagged: bool
    reason: str | None = None
    matched_terms: list[str] = field(default_factory=list)
    forbidden_terms: list[str] = field(default_factory=list)
    unknown_terms: list[str] = field(default_factory=list)
    allowed_labels: list[str] = field(default_factory=list)

    def to_metadata(self) -> dict:
        return {
            "score": self.score,
            "flagged": self.flagged,
            "reason": self.reason,
            "matched_terms": self.matched_terms,
            "forbidden_terms": self.forbidden_terms,
            "unknown_terms": self.unknown_terms,
            "allowed_labels": self.allowed_labels,
        }


class ConformityValidator:
    """
    Validate that classification language in query/answer conforms to the ontology.

    Flags when forbidden labels are requested or asserted, or when unknown labels appear.
    """

    def __init__(self, taxonomy: Taxonomy | None = None, taxonomy_path: Path | None = None) -> None:
        self.taxonomy = taxonomy or load_taxonomy(taxonomy_path)
        self.settings = get_settings()

    def validate(
        self,
        query: str,
        answer: str,
        contexts: list[str] | None = None,
    ) -> ConformityResult:
        context_texts = contexts or []
        query_terms = extract_classification_terms(query)
        answer_only_terms = extract_classification_terms(answer)
        context_terms = extract_classification_terms(*context_texts) if context_texts else []
        answer_terms = sorted(set(answer_only_terms) | set(context_terms))

        # Query requesting forbidden classification is always flagged
        query_linked = link_terms(query_terms, self.taxonomy)
        forbidden_in_query = _forbidden_from_linked(query_linked)

        answer_linked = link_terms(answer_terms, self.taxonomy)
        forbidden_in_answer = [
            lt.matched_label
            for lt in answer_linked
            if lt.is_forbidden
            and lt.matched_label
            and not _is_negated_mention(answer, lt.term, canonical=lt.matched_label)
        ]
        forbidden_in_answer = _collapse_forbidden_labels(forbidden_in_answer)
        # Unknown labels: query + generated answer only (not figure captions in retrieved context)
        unknown_source = sorted(set(query_terms + answer_only_terms))
        unknown_linked = link_terms(unknown_source, self.taxonomy)
        unknown_in_answer = [lt.term for lt in unknown_linked if lt.matched_label is None and lt.term]
        allowed_matches = [
            lt.matched_label
            for lt in answer_linked
            if lt.matched_label and not lt.is_forbidden
        ]

        all_forbidden = _collapse_forbidden_labels(forbidden_in_query + forbidden_in_answer)
        if all_forbidden:
            labels = ", ".join(self.taxonomy.allowed_labels)
            forbidden_str = ", ".join(all_forbidden)
            return ConformityResult(
                score=0.0,
                flagged=True,
                reason=(
                    f"Forbidden classification label(s): {forbidden_str}. "
                    f"Allowed labels: {labels}."
                ),
                matched_terms=allowed_matches,
                forbidden_terms=all_forbidden,
                unknown_terms=unknown_in_answer,
                allowed_labels=self.taxonomy.allowed_labels,
            )

        if unknown_in_answer:
            labels = ", ".join(self.taxonomy.allowed_labels)
            unknown_str = ", ".join(unknown_in_answer)
            return ConformityResult(
                score=0.0,
                flagged=True,
                reason=f"Unknown classification label(s): {unknown_str}. Allowed: {labels}.",
                forbidden_terms=[],
                unknown_terms=unknown_in_answer,
                allowed_labels=self.taxonomy.allowed_labels,
            )

        # No classification language — not a taxonomy-sensitive response
        if not query_terms and not answer_terms:
            return ConformityResult(
                score=1.0,
                flagged=False,
                reason=None,
                allowed_labels=self.taxonomy.allowed_labels,
            )

        # Allowed labels only
        if allowed_matches or not answer_terms:
            return ConformityResult(
                score=1.0,
                flagged=False,
                matched_terms=allowed_matches,
                allowed_labels=self.taxonomy.allowed_labels,
            )

        return ConformityResult(
            score=0.5,
            flagged=False,
            reason="Classification terms present but not linked to taxonomy.",
            allowed_labels=self.taxonomy.allowed_labels,
        )

    def should_block(self, result: ConformityResult) -> bool:
        return result.flagged and result.score < self.settings.eval_conformity_threshold
