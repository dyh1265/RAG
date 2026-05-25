"""
Central configuration using pydantic-settings.
Everything in the backend imports from here — no scattered os.getenv() calls.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM Providers ---
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
    openai_vision_model: str = "gpt-4o"
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = "llama3.2"

    # --- Embedding Models ---
    text_embedding_model: str = "BAAI/bge-m3"
    image_embedding_model: str = "laion/CLIP-ViT-B-32-laion2B-s34B-b79K"
    colpali_model: str = Field(default="vidore/colqwen2-v1.0", alias="COLPALI_MODEL")
    use_colpali: bool = Field(default=False, alias="USE_COLPALI")
    use_hybrid: bool = Field(default=False, alias="USE_HYBRID")
    use_recursive_chunker: bool = Field(default=False, alias="USE_RECURSIVE_CHUNKER")
    use_semantic_chunker: bool = Field(default=False, alias="USE_SEMANTIC_CHUNKER")
    use_section_paths: bool = Field(default=True, alias="USE_SECTION_PATHS")
    use_context_enrichment: bool = Field(default=True, alias="USE_CONTEXT_ENRICHMENT")
    use_parent_expand: bool = Field(default=True, alias="USE_PARENT_EXPAND")
    use_flashrank: bool = Field(default=False, alias="USE_FLASHRANK")
    semantic_chunk_threshold: float = Field(default=0.75, alias="SEMANTIC_CHUNK_THRESHOLD")
    embedding_batch_size: int = 32
    embedding_device: str = "cpu"  # "cuda" if GPU available

    # --- Vector DB (Qdrant) ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")
    qdrant_collection_text: str = "text_chunks"
    qdrant_collection_tables: str = "table_chunks"
    qdrant_collection_figures: str = "figure_chunks"
    qdrant_collection_pages: str = "page_chunks"
    qdrant_upsert_batch_size: int = 64

    # --- Redis ---
    redis_url: str = "redis://localhost:6379"
    embedding_cache_ttl_seconds: int = 86400 * 7  # 1 week
    celery_broker_url: str = Field(default="", alias="CELERY_BROKER_URL")
    ingest_metrics_port: int = Field(default=9100, alias="INGEST_METRICS_PORT")
    dedup_similarity_threshold: float = Field(default=0.85, alias="DEDUP_SIMILARITY_THRESHOLD")

    # --- Document Processing ---
    data_dir: str = "data"
    raw_docs_dir: str = "data/raw"
    processed_docs_dir: str = "data/processed"
    taxonomies_dir: str = "data/taxonomies"
    max_chunk_size: int = 512        # tokens
    chunk_overlap: int = 64          # tokens
    max_workers: int = 4             # async ingestion workers
    use_ocr: bool = Field(default=True, alias="USE_OCR")
    ocr_lang: str = Field(default="eng", alias="OCR_LANG")

    # --- Retrieval ---
    default_top_k: int = 5
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_top_n: int = 3

    # --- Evaluation ---
    eval_faithfulness_threshold: float = 0.85
    eval_keyword_coverage_threshold: float = Field(default=0.66, alias="EVAL_KEYWORD_COVERAGE_THRESHOLD")
    eval_recall_at_5_threshold: float = Field(default=0.70, alias="EVAL_RECALL_AT_5_THRESHOLD")
    eval_hit_at_5_threshold: float = Field(default=0.80, alias="EVAL_HIT_AT_5_THRESHOLD")
    eval_mrr_threshold: float = Field(default=0.50, alias="EVAL_MRR_THRESHOLD")
    eval_conformity_threshold: float = 0.90
    eval_latency_p95_ms: float = Field(
        default=60_000.0,
        alias="EVAL_LATENCY_P95_MS",
        description="p95 retrieve+answer wall-clock budget for eval tests (ms)",
    )
    eval_retrieval_latency_p95_ms: float = Field(
        default=60_000.0,
        alias="EVAL_RETRIEVAL_LATENCY_P95_MS",
        description="p95 retrieve-only budget for eval tests after warmup (ms)",
    )
    eval_regression_tolerance: float = 0.05  # 5% drop triggers alert
    use_taxonomy_validation: bool = Field(default=True, alias="USE_TAXONOMY_VALIDATION")
    taxonomy_block_forbidden: bool = Field(default=False, alias="TAXONOMY_BLOCK_FORBIDDEN")

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_rate_limit_per_minute: int = 60
    use_pii_redaction: bool = Field(default=True, alias="USE_PII_REDACTION")
    use_pii_redaction_on_ingest: bool = Field(default=True, alias="USE_PII_REDACTION_ON_INGEST")
    api_warmup_models: bool = Field(default=True, alias="API_WARMUP_MODELS")

    # --- Observability ---
    log_level: str = "INFO"
    otlp_endpoint: str = "http://localhost:4317"
    prometheus_port: int = 9090


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
