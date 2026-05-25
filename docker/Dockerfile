# Production RAG API — FastAPI + multimodal pipeline + taxonomy + guardrails.
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    EMBEDDING_DEVICE=cpu \
    USE_COLPALI=false \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install \
        "pydantic>=2.0" \
        "pydantic-settings>=2.0" \
        "python-dotenv>=1.0" \
        "pymupdf>=1.24" \
        "pdfplumber>=0.11" \
        "qdrant-client>=1.12.0,<1.13.0" \
        "httpx>=0.27" \
        "sentence-transformers>=3.4.0,<6.0.0" \
        "open_clip_torch>=2.24" \
        "rank-bm25>=0.2" \
        "langchain-text-splitters>=0.3" \
        "tiktoken>=0.7" \
        "flashrank>=0.2" \
        "rdflib>=7.0" \
        "rapidfuzz>=3.0" \
        "redis>=5.0" \
        "celery[redis]>=5.4" \
        "datasketch>=1.6" \
        "fastapi>=0.111" \
        "uvicorn[standard]>=0.30" \
        "python-multipart>=0.0.9" \
        "presidio-analyzer>=2.2" \
        "presidio-anonymizer>=2.2" \
        "spacy>=3.7" \
        "opentelemetry-sdk>=1.24" \
        "opentelemetry-exporter-otlp>=1.24" \
        "opentelemetry-instrumentation-fastapi>=0.45" \
        "slowapi>=0.1" \
        "tenacity>=8.3" \
        "prometheus-client>=0.20" \
        "pytesseract>=0.3" \
        "Pillow>=10.0" \
    && python -m spacy download en_core_web_sm

COPY backend/ backend/
COPY data/taxonomies/ data/taxonomies/

EXPOSE 8000

CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
