# Retrieval

Retrieval is the bulk of DocuMind's complexity. The goal: given a natural-language question, return the smallest set of chunks (text, tables, figures, optionally page images) that lets the LLM answer with citations. This page walks through every stage that lives under [`backend/retrieval/`](https://github.com/dyh1265/RAG/tree/master/backend/retrieval).

## High-level flow

```
question
  │
  ├── (optional) detect modality hint  →  bias which collection wins ties
  │
  ▼
┌─────────────────────────┐
│  per-collection search  │  ←  text / tables / figures / pages (parallel)
└─────────────────────────┘
  │
  ▼
hybrid (BM25 + dense) within text_chunks
  │
  ▼
Reciprocal Rank Fusion across collections
  │
  ▼
parent-chunk expansion
  │
  ▼
(optional) cross-encoder or FlashRank rerank
  │
  ▼
top-K → AnswerGenerator
```

## 1. Modality routing

Implemented in [`MultiModalRetriever`](https://github.com/dyh1265/RAG/blob/master/backend/retrieval/multimodal_retriever.py). The query is classified with cheap regex / keyword heuristics:

| Hint in the query | Collection biased |
|---|---|
| *"table", "row", "column", "Table N"* | `table_chunks` |
| *"figure", "chart", "Figure N", "plot"* | `figure_chunks` |
| *"on page N", "appendix"* | uses Qdrant `page_number` filter |
| *(no hint)* | all collections searched equally |

This is intentionally lightweight — the hint *biases* but doesn't *gate*. A question like *"what does Figure 3 show"* still searches text in case the answer is in the figure's caption rather than the figure itself.

## 2. Hybrid retrieval (text only)

When `USE_HYBRID=true` (default in production), [`HybridRetriever`](https://github.com/dyh1265/RAG/blob/master/backend/retrieval/hybrid_retriever.py) combines:

- **Dense**: top-K nearest neighbours from Qdrant on the BGE-M3 embedding of the question.
- **Sparse**: BM25 over the same chunks, using `rank-bm25` with a tokenizer that handles numeric tokens and hyphenated terms.

The two lists are merged with **Reciprocal Rank Fusion**:

```
score(c) = Σ over retrievers r:  1 / (k + rank_r(c))      where k = 60
```

RRF is rank-based rather than score-based, so we don't need to normalize the BM25 and cosine scales — a long-standing source of fragility in hybrid search.

> Why both? BGE-M3 dense vectors handle synonyms ("revenue" ≈ "income") and paraphrasing; BM25 handles exact strings the embedder doesn't care about ("Q4 2024", "$191.7M"). The combination beats either alone on the golden set.

## 3. Multimodal fusion (across collections)

After per-collection retrieval, RRF runs again — this time fusing the top results from `text_chunks`, `table_chunks`, `figure_chunks`, and (if enabled) `page_chunks`. Modality hints simply add a small constant boost to the relevant collection's rank. The output is a single ranked list of `RetrievedContext` objects.

## 4. Parent-chunk expansion

When `USE_PARENT_EXPAND=true` (default), a hit on a small "child" chunk pulls in its neighbouring siblings to form a richer context. This solves the classic chunking trade-off:

- **Small chunks** (~256 tokens) rank well because they're focused, but they truncate the surrounding evidence.
- **Large chunks** (~1024 tokens) carry more context but rank worse because the signal-to-noise drops.

DocuMind embeds the small chunks but, on a hit, expands to the parent passage. See [`backend/retrieval/parent_expand.py`](https://github.com/dyh1265/RAG/blob/master/backend/retrieval/parent_expand.py).

## 5. Labeled-asset retrieval

Tables and figures often have explicit labels (*Table 1*, *Figure 3*). [`backend/retrieval/asset_refs.py`](https://github.com/dyh1265/RAG/blob/master/backend/retrieval/asset_refs.py) detects these references in both the query *and* the chunk metadata, and adds them as a high-precedence path on top of the vector / BM25 / RRF stack. This means *"What does Figure 3 show?"* directly retrieves the chunk that was labeled *Figure 3* by the parser at ingest time — no embedding match required.

## 6. Optional rerankers

Two rerankers are available, off by default:

| Reranker | Model | Latency (CPU) | When to use |
|---|---|---|---|
| **Cross-encoder** ([`CrossEncoderReranker`](https://github.com/dyh1265/RAG/blob/master/backend/retrieval/cross_encoder_reranker.py)) | `BAAI/bge-reranker-v2-m3` | ~250 ms for 10 chunks | Best quality, ~10× slower than no reranker. |
| **FlashRank** ([`FlashRankReranker`](https://github.com/dyh1265/RAG/blob/master/backend/retrieval/flashrank_reranker.py)) | ms-marco-MiniLM-L-12-v2 | ~25 ms | Solid quality, almost free latency. Set `USE_FLASHRANK=true`. |

Both shrink the retrieved-context list from `default_top_k=5` down to `reranker_top_n=3` before the LLM call, which also makes the LLM cheaper.

## 7. ColPali (page-image retrieval)

When `USE_COLPALI=true`, DocuMind also embeds *whole rendered pages* with a vision-language model (default `vidore/colqwen2-v1.0`). This is useful for documents where the layout itself encodes information (forms, multi-column scientific papers, slide decks) — the text embedder loses that, but ColPali doesn't.

Practical notes:
- ColPali needs a GPU to be tolerable. Use `vidore/colSmol-500M` for CPU.
- It's purely additive: the `page_chunks` collection participates in RRF fusion just like text/tables/figures.

## 8. Chunk filters

[`backend/retrieval/chunk_filters.py`](https://github.com/dyh1265/RAG/blob/master/backend/retrieval/chunk_filters.py) runs cheap post-retrieval filters before the LLM call:

- `is_substantive_content`: drops chunks whose visible text is whitespace, single characters, or page numbers — common artefacts from OCR on scanned PDFs.
- Dedup by `chunk_id`: same chunk surfacing from both dense and sparse retrieval is collapsed.

If every retrieved chunk fails `is_substantive_content`, the generator short-circuits to the "no searchable text" fallback rather than asking the LLM to answer from nothing.

## Why this stack

| Choice | Alternative considered | Why we picked this |
|---|---|---|
| Hybrid (BM25 + dense) + RRF | Dense only | Real questions cite specific numbers and identifiers. Dense alone misses them; RRF without rescaling is robust. |
| Separate collection per modality | One collection with a `type` filter | Different embedding models per modality means different vector dimensionalities. Qdrant needs separate collections. |
| Parent expansion | Larger chunks at ingest | Decouples *what we index for ranking* from *what we feed the LLM*. |
| Optional rerankers | Always-on reranker | Quality / latency knob the operator owns. CI runs without; production can flip the toggle. |
| ColPali behind a flag | Always-on | Costs a GPU; only worth it for layout-heavy corpora. |

See [Evaluation](Evaluation) for how each of these is measured against the golden set.
