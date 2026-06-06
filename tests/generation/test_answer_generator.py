"""Tests for answer generation and citation building."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.core.models import ChunkType
from backend.generation.answer_generator import (
    AnswerGenerator,
    _build_context_block,
    _slide_scoped_hint,
)
from tests._factories import make_chunk, make_context


def test_generate_without_contexts():
    generator = AnswerGenerator(provider="ollama", model="llama3.2")
    response = generator.generate("What is revenue?", [])

    assert "No relevant context" in response.answer
    assert response.citations == []


def test_generate_openai_calls_api_and_builds_citations():
    generator = AnswerGenerator(provider="openai", model="gpt-4o-mini")
    generator.api_key = "sk-test-key"

    contexts = [
        make_context(
            chunk_id="c1",
            content=(
                "Revenue was $58.3M in Q1 2025, up from $54.6M in Q4 2024. "
                "Operating margin reached 23.1%."
            ),
            rank=1,
        ),
        make_context(
            chunk_id="c2",
            content=(
                "Operating margin improved each quarter as infrastructure costs "
                "were amortised over a larger customer base."
            ),
            rank=2,
        ),
    ]

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Revenue reached $58.3M in Q1 2025 [1]."}}]
    }

    with patch("backend.generation.answer_generator.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        client.post.return_value = mock_response
        client_cls.return_value = client

        response = generator.generate("What was Q1 2025 revenue?", contexts)

    assert "58.3M" in response.answer
    assert response.model_used == "openai:gpt-4o-mini"
    assert len(response.citations) == 2
    assert response.citations[0].chunk_id == "c1"
    client.post.assert_called_once()
    call_kwargs = client.post.call_args
    assert call_kwargs[0][0] == "https://api.openai.com/v1/chat/completions"


def test_build_context_block_includes_section_for_pdf():
    chunk = make_chunk(
        chunk_id="rev",
        content=(
            "Figure 3 below shows quarterly revenue from Q1 2024 through Q1 2025. "
            "The chart illustrates a consistent upward trend."
        ),
        page_number=2,
    ).model_copy(
        update={
            "section_path": "Revenue Analysis",
            "context_prefix": "Document: sample report\nSection: Revenue Analysis",
        }
    )
    contexts = [make_context(chunk_id="rev", content=chunk.content, page_number=2)]
    contexts[0].chunk = chunk

    block = _build_context_block(contexts)
    assert 'section "Revenue Analysis"' in block
    assert "Section: Revenue Analysis" in block
    assert "Figure 3 below shows" in block


def test_build_context_block_youtube_slide_and_transcript():
    contexts = [
        make_context(
            chunk_id="slide-7",
            content="Slide title: Backdoor criterion",
            page_number=7,
        ),
        make_context(
            chunk_id="spoken",
            content="Now we discuss identification using observational distributions.",
            page_number=None,
        ),
    ]
    contexts[0].chunk.metadata = {
        "source_kind": "youtube",
        "modality": "slide",
        "slide_number": 7,
        "timestamp": 200.0,
    }
    contexts[0].chunk.chunk_type = ChunkType.TEXT
    contexts[1].chunk.metadata = {
        "source_kind": "youtube",
        "modality": "transcript",
        "start_time": 205.0,
        "end_time": 260.0,
        "aligned_slide_number": 7,
    }
    contexts[1].chunk.chunk_type = ChunkType.TRANSCRIPT

    block = _build_context_block(contexts)
    assert "Slide 7 on-screen text" in block
    assert "3:20" in block
    assert "Spoken during slide 7" in block
    assert "3:25–4:20" in block


def test_slide_scoped_hint_for_page_query():
    hint = _slide_scoped_hint("What did the author say about slide 7")
    assert "slide 7" in hint.lower()
    assert "spoken" in hint.lower()
    assert _slide_scoped_hint("what is a backdoor path") == ""


def test_generate_openai_includes_slide_hint_in_prompt():
    generator = AnswerGenerator(provider="openai", model="gpt-4o-mini")
    generator.api_key = "sk-test-key"

    chunk = make_chunk(
        chunk_id="spoken",
        chunk_type=ChunkType.TRANSCRIPT,
        content=(
            "The lecturer explains that do-free expressions imply identification "
            "from the observational distribution alone."
        ),
        page_number=None,
        metadata={
            "source_kind": "youtube",
            "modality": "transcript",
            "start_time": 205.0,
            "end_time": 260.0,
            "aligned_slide_number": 7,
        },
    )
    contexts = [
        make_context(chunk_id="spoken", content=chunk.content, page_number=None),
    ]
    contexts[0].chunk = chunk

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "The author explained identification [1]."}}]
    }

    with patch("backend.generation.answer_generator.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        client.post.return_value = mock_response
        client_cls.return_value = client

        generator.generate("What did the author say about slide 7", contexts)

    payload = client.post.call_args.kwargs["json"]
    user_content = payload["messages"][1]["content"]
    assert "Spoken during slide 7" in user_content
    assert "slide 7 of a video lecture" in user_content


def test_generate_openai_requires_api_key():
    generator = AnswerGenerator(provider="openai")
    generator.api_key = ""

    substantive = make_context(
        content=(
            "Revenue was $58.3M in Q1 2025, up from $54.6M in Q4 2024. "
            "Operating margin reached 23.1%."
        ),
    )

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        generator.generate("Q?", [substantive])
