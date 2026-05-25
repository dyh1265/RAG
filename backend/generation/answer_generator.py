"""
LLM answer generation with source citations.

Supports Ollama (local) and OpenAI. Falls back gracefully when the provider
is unreachable — callers can still use retrieved contexts.
"""

from __future__ import annotations

import httpx

from backend.retrieval.chunk_filters import is_substantive_content
from backend.core.config import get_settings
from backend.core.models import Citation, QueryResponse, RetrievedContext

_SYSTEM_PROMPT = (
    "You are a precise document QA assistant. Answer ONLY using the numbered "
    "context passages below. If the context lists items (practices, steps, "
    "principles, etc.), include the full list in your answer. "
    "If the context is insufficient, say so. "
    "Cite sources inline as [1], [2], etc."
)


def _chunk_type_label(chunk_type) -> str:
    return chunk_type.value if hasattr(chunk_type, "value") else str(chunk_type)


def _build_context_block(contexts: list[RetrievedContext]) -> str:
    blocks: list[str] = []
    for idx, ctx in enumerate(contexts, start=1):
        chunk = ctx.chunk
        page = chunk.page_number if chunk.page_number is not None else "?"
        label = _chunk_type_label(chunk.chunk_type)
        blocks.append(f"[{idx}] (page {page}, {label})\n{chunk.content.strip()}")
    return "\n\n".join(blocks)


def _build_citations(contexts: list[RetrievedContext]) -> list[Citation]:
    citations: list[Citation] = []
    for ctx in contexts:
        chunk = ctx.chunk
        excerpt = chunk.content.strip()
        if len(excerpt) > 240:
            excerpt = excerpt[:237] + "..."
        citations.append(
            Citation(
                doc_id=chunk.doc_id,
                source_path=chunk.source_path,
                page_number=chunk.page_number,
                chunk_id=chunk.id,
                excerpt=excerpt,
            )
        )
    return citations


class AnswerGenerator:
    """
    Generate an grounded answer from retrieved contexts.

    Usage
    -----
    generator = AnswerGenerator(provider="ollama")
    response = generator.generate(question, contexts)
    """

    def __init__(
        self,
        provider: str = "ollama",
        model: str | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        settings = get_settings()
        self.provider = provider.lower()
        self.timeout_seconds = timeout_seconds

        if self.provider == "openai":
            self.model = model or settings.openai_model
            self.api_key = settings.openai_api_key
        elif self.provider == "ollama":
            self.model = model or settings.ollama_model
            self.base_url = settings.ollama_base_url.rstrip("/")
        else:
            raise ValueError(f"Unsupported provider: {provider}. Use 'ollama' or 'openai'.")

    def generate(
        self,
        question: str,
        contexts: list[RetrievedContext],
        latency_ms: float | None = None,
    ) -> QueryResponse:
        if not contexts:
            return QueryResponse(
                query=question,
                answer=(
                    "No relevant context was retrieved for this question. "
                    "This document may be image-only (no searchable text was indexed). "
                    "Re-upload the PDF to run OCR at ingest, or select a fully indexed copy."
                ),
                citations=[],
                retrieved_contexts=[],
                model_used=self.model,
                latency_ms=latency_ms,
            )

        if not any(is_substantive_content(ctx.chunk.content) for ctx in contexts):
            return QueryResponse(
                query=question,
                answer=(
                    "This document has no searchable text in the index (scanned/image-only pages). "
                    "Re-upload the PDF to run OCR at ingest, or pick a different indexed document."
                ),
                citations=_build_citations(contexts),
                retrieved_contexts=contexts,
                model_used=self.model,
                latency_ms=latency_ms,
            )

        context_block = _build_context_block(contexts)
        user_prompt = f"Context:\n{context_block}\n\nQuestion: {question}\n\nAnswer:"

        if self.provider == "openai":
            answer = self._call_openai(user_prompt)
        else:
            answer = self._call_ollama(user_prompt)

        return QueryResponse(
            query=question,
            answer=answer.strip(),
            citations=_build_citations(contexts),
            retrieved_contexts=contexts,
            model_used=f"{self.provider}:{self.model}",
            latency_ms=latency_ms,
        )

    def _call_ollama(self, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ConnectionError(
                f"Ollama request failed ({self.base_url}). "
                f"Start Ollama and pull the model: ollama pull {self.model}"
            ) from exc

        data = response.json()
        message = data.get("message", {})
        content = message.get("content")
        if not content:
            raise RuntimeError(f"Unexpected Ollama response: {data}")
        return content

    def _call_openai(self, user_prompt: str) -> str:
        if not self.api_key or self.api_key.startswith("sk-..."):
            raise ValueError(
                "OPENAI_API_KEY is not set. Add it to .env or use --provider ollama."
            )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ConnectionError("OpenAI request failed. Check OPENAI_API_KEY and network.") from exc

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"Unexpected OpenAI response: {data}")
        return choices[0]["message"]["content"]
