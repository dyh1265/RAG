"""Tests for answer generation and citation building."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from phases.phase_01_multimodal_ingestion.generation.answer_generator import AnswerGenerator
from tests.phase1.conftest import make_context


def test_generate_without_contexts():
    generator = AnswerGenerator(provider="ollama", model="llama3.2")
    response = generator.generate("What is revenue?", [])

    assert "No relevant context" in response.answer
    assert response.citations == []


def test_generate_openai_calls_api_and_builds_citations():
    generator = AnswerGenerator(provider="openai", model="gpt-4o-mini")
    generator.api_key = "sk-test-key"

    contexts = [
        make_context(chunk_id="c1", content="Revenue was $58.3M in Q1 2025.", rank=1),
        make_context(chunk_id="c2", content="Operating margin improved.", rank=2),
    ]

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Revenue reached $58.3M in Q1 2025 [1]."}}]
    }

    with patch("phases.phase_01_multimodal_ingestion.generation.answer_generator.httpx.Client") as client_cls:
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


def test_generate_openai_requires_api_key():
    generator = AnswerGenerator(provider="openai")
    generator.api_key = ""

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        generator.generate("Q?", [make_context()])
