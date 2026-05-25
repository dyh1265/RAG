"""DocuMind capstone tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from capstone.pipeline import DocuMind, DocuMindConfig
from shared.models import QueryResponse


def test_documind_config_defaults():
    cfg = DocuMindConfig()
    assert cfg.use_hybrid is True
    assert cfg.use_recursive_chunker is True
    assert cfg.use_taxonomy_validation is True


def test_documind_ask_local():
    mock_response = QueryResponse(query="test", answer="ok", metadata={})
    pipeline = MagicMock()
    pipeline.query.return_value = mock_response

    with patch("capstone.pipeline.RAGPipeline", return_value=pipeline):
        dm = DocuMind(DocuMindConfig(llm_provider="openai"))
        out = dm.ask("test", doc_id="abc")
    assert out.answer == "ok"
    pipeline.query.assert_called_once()
