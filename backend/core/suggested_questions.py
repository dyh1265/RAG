"""Heuristic starter questions derived from indexed document chunks."""

from __future__ import annotations

from pathlib import Path

from backend.core.models import ChunkType, DocumentChunk

DEFAULT_SUGGESTIONS = [
    "Give me a brief overview of this document.",
    "What are the main takeaways?",
    "What topics does this document cover?",
]


def doc_title_from_name(name: str) -> str:
    stem = Path(name).stem if name else ""
    title = stem.replace("_", " ").replace("-", " ").strip()
    return title or "this document"


def _leaf_section(section_path: str) -> str:
    normalized = section_path.replace(">", "/")
    parts = [part.strip() for part in normalized.split("/") if part.strip()]
    return parts[-1] if parts else section_path.strip()


def build_suggested_questions(
    *,
    doc_name: str,
    chunks: list[DocumentChunk],
    max_questions: int = 3,
) -> list[str]:
    """Build up to ``max_questions`` document-specific starter prompts."""
    if max_questions <= 0:
        return []

    title = doc_title_from_name(doc_name)
    questions: list[str] = [f'Give me a brief overview of "{title}".']

    sections: list[str] = []
    seen_sections: set[str] = set()
    chunk_types: set[ChunkType] = set()

    for chunk in chunks:
        chunk_types.add(chunk.chunk_type)
        if not chunk.section_path:
            continue
        leaf = _leaf_section(chunk.section_path)
        key = leaf.lower()
        if key in seen_sections or len(leaf) <= 3 or len(leaf) > 80:
            continue
        seen_sections.add(key)
        sections.append(leaf)

    if sections:
        questions.append(f'What does the "{sections[0]}" section cover?')

    if ChunkType.TABLE in chunk_types and len(questions) < max_questions:
        questions.append("What are the key figures or data in the tables?")
    elif ChunkType.FIGURE in chunk_types and len(questions) < max_questions:
        questions.append("What do the charts or figures show?")
    elif len(sections) > 1 and len(questions) < max_questions:
        questions.append(f'Explain "{sections[1]}" in simple terms.')
    elif len(questions) < max_questions:
        questions.append("What are the main conclusions or recommendations?")

    while len(questions) < max_questions:
        fallback = DEFAULT_SUGGESTIONS[len(questions) % len(DEFAULT_SUGGESTIONS)]
        if fallback not in questions:
            questions.append(fallback)
        else:
            break

    return questions[:max_questions]
