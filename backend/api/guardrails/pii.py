"""Presidio-based PII redaction for ingest and query text."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import TYPE_CHECKING

from backend.core.config import get_settings

if TYPE_CHECKING:
    from backend.core.models import QueryResponse

# Contact/financial identifiers only.
# Omit US_DRIVER_LICENSE (false positives on job refs like "e02") and DATE_TIME (years, Q1–Q4).
_PII_ENTITY_TYPES = frozenset({
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "US_BANK_NUMBER",
    "IBAN_CODE",
    "US_PASSPORT",
    "IP_ADDRESS",
    "MEDICAL_LICENSE",
    "CRYPTO",
})
_FISCAL_QUARTER_RE = re.compile(r"^Q\d+$", re.IGNORECASE)


@lru_cache(maxsize=1)
def _engines():
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
    except ImportError as exc:
        raise ImportError(
            "presidio not installed; run `pip install -e .` from the repo root."
        ) from exc

    return AnalyzerEngine(), AnonymizerEngine()


class PIIRedactor:
    """Redact common PII entities before indexing or answering."""

    def __init__(self, *, language: str = "en", enabled: bool | None = None) -> None:
        self.language = language
        settings = get_settings()
        self._enabled = settings.use_pii_redaction if enabled is None else enabled
        self._analyzer = None
        self._anonymizer = None
        if not self._enabled:
            return
        try:
            self._analyzer, self._anonymizer = _engines()
        except ImportError:
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def redact(self, text: str) -> tuple[str, bool]:
        """Return (redacted_text, was_modified)."""
        if not text.strip() or not self._enabled:
            return text, False

        raw = self._analyzer.analyze(text=text, language=self.language)
        results = []
        for r in raw:
            span = text[r.start : r.end].strip()
            if _FISCAL_QUARTER_RE.match(span):
                continue
            if r.entity_type in _PII_ENTITY_TYPES:
                results.append(r)
        if not results:
            return text, False

        anonymized = self._anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized.text, anonymized.text != text

    def redact_response(self, response: "QueryResponse") -> tuple["QueryResponse", bool]:
        """Redact PII in answer, citation excerpts, and retrieved chunk text."""
        modified = False
        new_citations = []
        for cite in response.citations:
            excerpt, changed = self.redact(cite.excerpt)
            modified |= changed
            new_citations.append(cite.model_copy(update={"excerpt": excerpt}))

        new_contexts = []
        for ctx in response.retrieved_contexts:
            content, changed = self.redact(ctx.chunk.content)
            if changed:
                modified = True
                chunk = ctx.chunk.model_copy(update={"content": content})
                ctx = ctx.model_copy(update={"chunk": chunk})
            new_contexts.append(ctx)

        answer, changed = self.redact(response.answer)
        modified |= changed

        return (
            response.model_copy(
                update={
                    "answer": answer,
                    "citations": new_citations,
                    "retrieved_contexts": new_contexts,
                }
            ),
            modified,
        )


def redact_chunk_contents(chunks: list) -> bool:
    """Redact PII in chunk text before indexing. Returns True if any chunk changed."""
    settings = get_settings()
    if not settings.use_pii_redaction or not settings.use_pii_redaction_on_ingest:
        return False

    redactor = PIIRedactor()
    if not redactor.enabled:
        return False

    modified = False
    for i, chunk in enumerate(chunks):
        redacted, changed = redactor.redact(chunk.content)
        if changed:
            modified = True
            chunks[i] = chunk.model_copy(update={"content": redacted})
    return modified
