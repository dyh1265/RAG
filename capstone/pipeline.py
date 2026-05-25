"""
DocuMind — capstone facade over Phases 1–6.

Composes RAGPipeline (local) or the Phase 6 HTTP API (remote) with
enterprise defaults: hybrid retrieval, recursive chunking, taxonomy validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from phases.phase_01_multimodal_ingestion.parsers.base_parser import stable_doc_id
from shared.config import Settings, get_settings
from shared.models import QueryRequest, QueryResponse
from shared.pipeline import IngestResult, PipelineConfig, RAGPipeline


@dataclass
class DocuMindConfig:
    """Opinionated defaults for the capstone demo path."""

    use_hybrid: bool = True
    use_recursive_chunker: bool = True
    use_section_paths: bool = True
    use_context_enrichment: bool = True
    use_parent_expand: bool = True
    use_flashrank: bool = False
    use_colpali: bool = False
    text_only: bool = False
    use_taxonomy_validation: bool = True
    block_forbidden_classifications: bool = False
    llm_provider: str = "openai"
    top_k: int = 5

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> DocuMindConfig:
        s = settings or get_settings()
        return cls(
            use_hybrid=s.use_hybrid or True,
            use_recursive_chunker=s.use_recursive_chunker or True,
            use_section_paths=s.use_section_paths,
            use_context_enrichment=s.use_context_enrichment,
            use_parent_expand=s.use_parent_expand,
            use_flashrank=s.use_flashrank,
            use_colpali=False if s.use_colpali is False else s.use_colpali,
            use_taxonomy_validation=s.use_taxonomy_validation,
            block_forbidden_classifications=s.taxonomy_block_forbidden,
            llm_provider="openai" if s.openai_api_key else "ollama",
            top_k=s.default_top_k,
        )

    def to_pipeline_config(self) -> PipelineConfig:
        use_colpali = not self.text_only and self.use_colpali
        return PipelineConfig(
            use_colpali=use_colpali,
            use_hybrid=self.use_hybrid,
            use_recursive_chunker=self.use_recursive_chunker,
            use_section_paths=self.use_section_paths,
            use_context_enrichment=self.use_context_enrichment,
            use_parent_expand=self.use_parent_expand,
            use_flashrank=self.use_flashrank,
            use_taxonomy_validation=self.use_taxonomy_validation,
            block_forbidden_classifications=self.block_forbidden_classifications,
            llm_provider=self.llm_provider,
            text_only=self.text_only,
        )


class DocuMind:
    """
    Unified DocuMind entry point — local pipeline or remote API.

    Usage
    -----
    dm = DocuMind()
    dm.ingest("data/raw/sample_report.pdf")
    response = dm.ask("What was Q4 revenue?", doc="data/raw/sample_report.pdf")

    dm = DocuMind(api_url="http://localhost:8002")
    response = dm.ask("What was Q4 revenue?", doc_id="ed7d53f9b08caa39")
    """

    def __init__(
        self,
        config: DocuMindConfig | None = None,
        *,
        api_url: str | None = None,
    ) -> None:
        self.config = config or DocuMindConfig.from_settings()
        self.api_url = api_url.rstrip("/") if api_url else None
        self._pipeline: RAGPipeline | None = None
        if not self.api_url:
            self._pipeline = RAGPipeline(self.config.to_pipeline_config())

    @property
    def pipeline(self) -> RAGPipeline:
        if self._pipeline is None:
            raise RuntimeError("Local pipeline unavailable when using api_url mode")
        return self._pipeline

    def preload_models(self) -> float:
        if self.api_url:
            return 0.0
        return self.pipeline.preload_models()

    def ingest(self, path: str | Path) -> IngestResult:
        pdf_path = Path(path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"Document not found: {pdf_path}")

        if self.api_url:
            from capstone.client import DocuMindApiClient

            return DocuMindApiClient(self.api_url).ingest(pdf_path)

        return self.pipeline.ingest(pdf_path)

    def ask(
        self,
        query: str,
        *,
        doc: str | Path | None = None,
        doc_id: str | None = None,
        top_k: int | None = None,
        provider: str | None = None,
        retrieve_only: bool = False,
        block_forbidden: bool | None = None,
    ) -> QueryResponse:
        resolved_doc_id = doc_id
        if doc is not None:
            resolved_doc_id = stable_doc_id(doc)
        if not resolved_doc_id:
            raise ValueError("Provide doc path or doc_id")

        if self.api_url:
            from capstone.client import DocuMindApiClient

            return DocuMindApiClient(self.api_url).ask(
                query,
                doc_id=resolved_doc_id,
                top_k=top_k or self.config.top_k,
                provider=provider or self.config.llm_provider,
                retrieve_only=retrieve_only,
                block_forbidden=block_forbidden,
            )

        if block_forbidden is not None:
            self.pipeline.config.block_forbidden_classifications = block_forbidden

        request = QueryRequest(
            query=query,
            top_k=top_k or self.config.top_k,
            filters={"doc_id": resolved_doc_id},
        )
        return self.pipeline.query(
            request,
            generate_answer=not retrieve_only,
            provider=provider or self.config.llm_provider,
        )
