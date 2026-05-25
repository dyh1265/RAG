"""
Qdrant vector store wrapper.
Handles collection creation, upserting embedded chunks, and similarity search.
"""

from __future__ import annotations

from shared.config import get_settings
from shared.models import ChunkType, DocumentChunk, DocumentType, EmbeddedChunk, RetrievalStrategy, RetrievedContext

COLPALI_PAGE_DIM = 128
TEXT_PAGE_DIM = 1024


COLLECTION_MAP: dict[ChunkType, str] = {
    ChunkType.TEXT: "text_chunks",
    ChunkType.TABLE: "table_chunks",
    ChunkType.FIGURE: "figure_chunks",
    ChunkType.PAGE_IMAGE: "page_chunks",
    ChunkType.HEADING: "text_chunks",  # headings go into the text collection
}


def page_index_status(store: "QdrantStore", use_colpali: bool) -> str | None:
    """Return a warning when page_chunks dimension does not match query mode."""
    collection = COLLECTION_MAP[ChunkType.PAGE_IMAGE]
    stored = store.collection_vector_size(collection)
    expected = COLPALI_PAGE_DIM if use_colpali else TEXT_PAGE_DIM
    if stored is None:
        return (
            f"Collection '{collection}' is empty or missing — "
            "run without --skip-ingest to index the document."
        )
    if stored != expected:
        mode = f"ColPali ({COLPALI_PAGE_DIM}-dim)" if use_colpali else f"bge-m3 text ({TEXT_PAGE_DIM}-dim)"
        return (
            f"'{collection}' is indexed at {stored}-dim but query mode expects "
            f"{expected}-dim ({mode}). Re-run without --skip-ingest."
        )
    return None


def _qdrant_retry(call):
    """Retry transient Qdrant failures when tenacity is installed."""
    try:
        from tenacity import Retrying, stop_after_attempt, wait_exponential

        for attempt in Retrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.25, min=0.25, max=2),
            reraise=True,
        ):
            with attempt:
                return call()
    except ImportError:
        return call()


class QdrantStore:
    """
    Unified interface over Qdrant collections.

    Each chunk type is stored in its own collection so retrieval strategies
    can be applied independently (e.g. ColPali for figures, BM25+dense for text).

    Install: pip install qdrant-client
    """

    def __init__(self, url: str | None = None, api_key: str | None = None) -> None:
        settings = get_settings()
        self.url = url or settings.qdrant_url
        self.api_key = api_key or settings.qdrant_api_key or None
        self.upsert_batch_size = settings.qdrant_upsert_batch_size
        self._client = None  # lazy init

    @property
    def client(self):
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError:
                raise ImportError("Install qdrant-client: pip install qdrant-client")
            self._client = QdrantClient(
                url=self.url,
                api_key=self.api_key,
                timeout=120,
            )
        return self._client

    def collection_vector_size(self, collection_name: str) -> int | None:
        """Return configured vector dimension for a collection, or None if missing."""
        existing = {c.name for c in self.client.get_collections().collections}
        if collection_name not in existing:
            return None
        info = self.client.get_collection(collection_name)
        vectors_config = info.config.params.vectors
        if hasattr(vectors_config, "size"):
            return vectors_config.size
        return next(iter(vectors_config.values())).size

    def ensure_collection(self, collection_name: str, vector_size: int) -> None:
        """Create collection if missing; recreate when vector dimension changes."""
        from qdrant_client.models import Distance, VectorParams

        existing = {c.name for c in self.client.get_collections().collections}
        if collection_name in existing:
            current_size = self.collection_vector_size(collection_name)
            if current_size == vector_size:
                return
            self.client.delete_collection(collection_name)

        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    def upsert(self, embedded_chunks: list[EmbeddedChunk]) -> None:
        """Upsert a batch of embedded chunks into the appropriate collection."""
        from qdrant_client.models import PointStruct

        # Group by collection
        batches: dict[str, list[EmbeddedChunk]] = {}
        for ec in embedded_chunks:
            col = COLLECTION_MAP.get(ec.chunk.chunk_type, "text_chunks")
            batches.setdefault(col, []).append(ec)

        for collection_name, batch in batches.items():
            if not batch:
                continue
            vector_size = len(batch[0].vector)
            self.ensure_collection(collection_name, vector_size)

            points = [
                PointStruct(
                    id=ec.chunk.id,
                    vector=ec.vector,
                    payload={
                        "doc_id": ec.chunk.doc_id,
                        "source_path": ec.chunk.source_path,
                        "chunk_type": ec.chunk.chunk_type.value,
                        "content": ec.chunk.content,
                        "page_number": ec.chunk.page_number,
                        "section_path": ec.chunk.section_path,
                        "context_prefix": ec.chunk.context_prefix,
                        "image_path": ec.chunk.image_path,
                        "metadata": ec.chunk.metadata,
                    },
                )
                for ec in batch
            ]
            for start in range(0, len(points), self.upsert_batch_size):
                chunk = points[start : start + self.upsert_batch_size]
                _qdrant_retry(
                    lambda c=chunk, col=collection_name: self.client.upsert(
                        collection_name=col, points=c
                    )
                )

    def delete_doc(self, doc_id: str) -> None:
        """Remove all vectors for a document across every chunk collection."""
        from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

        selector = FilterSelector(
            filter=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            )
        )
        existing = {c.name for c in self.client.get_collections().collections}
        for collection_name in set(COLLECTION_MAP.values()):
            if collection_name in existing:
                self.client.delete(collection_name=collection_name, points_selector=selector)

    def list_documents(self, *, limit: int = 100) -> list[dict]:
        """Aggregate indexed documents by doc_id across all chunk collections."""
        docs: dict[str, dict] = {}
        existing = {c.name for c in self.client.get_collections().collections}
        for collection_name in set(COLLECTION_MAP.values()):
            if collection_name not in existing:
                continue
            offset = None
            while True:
                records, offset = self.client.scroll(
                    collection_name=collection_name,
                    limit=256,
                    offset=offset,
                    with_payload=["doc_id", "source_path"],
                    with_vectors=False,
                )
                if not records:
                    break
                for record in records:
                    payload = record.payload or {}
                    doc_id = payload.get("doc_id")
                    if not doc_id:
                        continue
                    if doc_id not in docs:
                        docs[doc_id] = {
                            "doc_id": doc_id,
                            "source_path": payload.get("source_path") or "",
                            "chunk_count": 0,
                        }
                    docs[doc_id]["chunk_count"] += 1
                if offset is None:
                    break
        return sorted(docs.values(), key=lambda d: d["doc_id"])[:limit]

    def get_document_source_path(self, doc_id: str) -> str | None:
        """Return source_path for doc_id from any chunk collection."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        existing = {c.name for c in self.client.get_collections().collections}
        for collection_name in set(COLLECTION_MAP.values()):
            if collection_name not in existing:
                continue
            records, _ = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
                ),
                limit=1,
                with_payload=["source_path"],
                with_vectors=False,
            )
            if not records:
                continue
            payload = records[0].payload or {}
            source_path = payload.get("source_path") or ""
            if source_path:
                return source_path
        return None

    @staticmethod
    def _payload_to_chunk(payload: dict, point_id: str) -> DocumentChunk:
        chunk_type = payload["chunk_type"]
        if isinstance(chunk_type, str):
            try:
                chunk_type = ChunkType(chunk_type)
            except ValueError:
                chunk_type = ChunkType.TEXT
        return DocumentChunk(
            id=str(point_id),
            doc_id=payload["doc_id"],
            source_path=payload["source_path"],
            doc_type=DocumentType.PDF,
            chunk_type=chunk_type,
            content=payload["content"],
            page_number=payload.get("page_number"),
            section_path=payload.get("section_path"),
            context_prefix=payload.get("context_prefix"),
            image_path=payload.get("image_path"),
            metadata=payload.get("metadata", {}),
        )

    def scroll_collection(
        self,
        collection_name: str,
        *,
        filters: dict | None = None,
        limit: int | None = None,
    ) -> list[DocumentChunk]:
        """Load chunks from Qdrant for in-memory BM25 or inspection."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        qdrant_filter = None
        if filters:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filters.items()
            ]
            qdrant_filter = Filter(must=conditions)

        existing = {c.name for c in self.client.get_collections().collections}
        if collection_name not in existing:
            return []

        chunks: list[DocumentChunk] = []
        offset = None
        while limit is None or len(chunks) < limit:
            batch_limit = 256 if limit is None else min(256, limit - len(chunks))
            records, offset = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=qdrant_filter,
                limit=batch_limit,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            if not records:
                break
            for record in records:
                if record.payload:
                    chunks.append(self._payload_to_chunk(record.payload, str(record.id)))
            if offset is None:
                break
        return chunks

    def get_chunks_by_ids(
        self,
        collection_name: str,
        chunk_ids: set[str],
    ) -> list[DocumentChunk]:
        """Fetch chunks by point id (used for parent-expand)."""
        if not chunk_ids:
            return []

        existing = {c.name for c in self.client.get_collections().collections}
        if collection_name not in existing:
            return []

        records = self.client.retrieve(
            collection_name=collection_name,
            ids=list(chunk_ids),
            with_payload=True,
            with_vectors=False,
        )
        chunks: list[DocumentChunk] = []
        for record in records:
            if record.payload:
                chunks.append(self._payload_to_chunk(record.payload, str(record.id)))
        return chunks

    def search(
        self,
        query_vector: list[float],
        collection_name: str,
        top_k: int = 5,
        filters: dict | None = None,
    ) -> list[RetrievedContext]:
        """Semantic similarity search in one collection."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        existing = {c.name for c in self.client.get_collections().collections}
        if collection_name not in existing:
            return []

        qdrant_filter = None
        if filters:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filters.items()
            ]
            qdrant_filter = Filter(must=conditions)

        expected_dim = self.collection_vector_size(collection_name)
        if expected_dim is not None and len(query_vector) != expected_dim:
            raise ValueError(
                f"Vector dimension mismatch for '{collection_name}': "
                f"collection expects {expected_dim}, query vector is {len(query_vector)}. "
                "Re-ingest without --skip-ingest when switching ColPali on or off "
                "(page_chunks uses 128-dim ColPali vs 1024-dim bge-m3 text)."
            )

        response = _qdrant_retry(
            lambda: self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=top_k * 3,
                query_filter=qdrant_filter,
                with_payload=True,
            )
        )
        hits = response.points

        results: list[RetrievedContext] = []
        seen_content: set[str] = set()
        for hit in hits:
            p = hit.payload
            content = p["content"]
            if content in seen_content:
                continue
            seen_content.add(content)

            chunk = self._payload_to_chunk(p, str(hit.id))
            results.append(RetrievedContext(
                chunk=chunk,
                score=hit.score,
                strategy=RetrievalStrategy.DENSE,
                rank=len(results) + 1,
            ))
            if len(results) >= top_k:
                break
        return results

    def search_collections(
        self,
        query_vector: list[float],
        collection_names: list[str],
        top_k: int = 5,
        filters: dict | None = None,
    ) -> list[RetrievedContext]:
        """Search multiple collections, merge by score, dedupe by content."""
        merged: list[RetrievedContext] = []
        for collection_name in collection_names:
            merged.extend(
                self.search(
                    query_vector,
                    collection_name=collection_name,
                    top_k=top_k,
                    filters=filters,
                )
            )

        merged.sort(key=lambda r: r.score, reverse=True)

        results: list[RetrievedContext] = []
        seen_content: set[str] = set()
        for ctx in merged:
            if ctx.chunk.content in seen_content:
                continue
            seen_content.add(ctx.chunk.content)
            results.append(
                RetrievedContext(
                    chunk=ctx.chunk,
                    score=ctx.score,
                    strategy=ctx.strategy,
                    rank=len(results) + 1,
                )
            )
            if len(results) >= top_k:
                break
        return results
