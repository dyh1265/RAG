# Fix Internal Server Error on /query (torch 2.5 + transformers 5.9)

- [x] Diagnose: docker logs show `ValueError` from `check_torch_load_is_safe` (torch 2.5.1+cu121, transformers 5.9)
- [x] Pin `torch>=2.6` in Dockerfile; GPU default index `cu124` (cu121 caps at 2.5.1)
- [x] Block startup until model warmup completes (or record failure in `/ready`)
- [x] `/query` returns 503 with actionable message on torch/transformers mismatch

## Review (after implementation)

- verification run: user must `docker compose ... build rag-api ingest-worker` and confirm `torch>=2.6` in container
- behavior diff notes: `/ready` reports `models: ok|warming|error`; warmup is awaited at startup; GPU default cu124
- residual risks: hosts without CUDA 12.4 driver may need different TORCH_INDEX_URL; first rebuild re-downloads wheels
