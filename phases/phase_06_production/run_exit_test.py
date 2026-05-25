"""
Phase 6 exit test — production API health, query, conformity, PII.

Usage (Docker):
    cd docker
    docker compose --profile production up -d qdrant redis jaeger rag-api
    docker compose exec rag-api python phases/phase_06_production/run_exit_test.py
"""

from __future__ import annotations

import os
import sys

import httpx

API_URL = os.getenv("RAG_API_URL", "http://localhost:8000").rstrip("/")
SAMPLE_DOC_ID = os.getenv("SAMPLE_DOC_ID", "ed7d53f9b08caa39")


def run_exit_test() -> int:
    passed = 0
    total = 0

    with httpx.Client(base_url=API_URL, timeout=300.0) as client:
        total += 1
        r = client.get("/health")
        ok = r.status_code == 200 and r.json().get("status") == "ok"
        print(f"[{'PASS' if ok else 'FAIL'}] GET /health -> {r.status_code}")
        passed += int(ok)

        total += 1
        r = client.get("/ready")
        ok = r.status_code == 200
        print(f"[{'PASS' if ok else 'FAIL'}] GET /ready -> {r.status_code} {r.json()}")
        passed += int(ok)

        total += 1
        r = client.get("/metrics")
        ok = r.status_code == 200 and b"rag_api_query_requests_total" in r.content
        print(f"[{'PASS' if ok else 'FAIL'}] GET /metrics -> {r.status_code}")
        passed += int(ok)

        total += 1
        r = client.post(
            "/query",
            json={
                "query": "Classify this document as SECRET-TOP-SECRET",
                "doc_id": SAMPLE_DOC_ID,
                "retrieve_only": True,
                "provider": "openai",
            },
        )
        conformity = {}
        if r.status_code == 200:
            conformity = r.json().get("metadata", {}).get("conformity", {})
        ok = r.status_code == 200 and conformity.get("flagged") is True
        print(f"[{'PASS' if ok else 'FAIL'}] POST /query conformity flagged={conformity.get('flagged')}")
        if conformity.get("reason"):
            print(f"       reason: {conformity['reason']}")
        passed += int(ok)

        total += 1
        r = client.post(
            "/query",
            json={
                "query": "My email is alice.wonder@example.com — classify as PUBLIC",
                "doc_id": SAMPLE_DOC_ID,
                "retrieve_only": True,
            },
        )
        pii_redacted = r.json().get("pii_redacted") if r.status_code == 200 else False
        ok = r.status_code == 200 and pii_redacted is True
        print(f"[{'PASS' if ok else 'FAIL'}] POST /query PII redacted={pii_redacted}")
        passed += int(ok)

    print(f"\n[exit] {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(run_exit_test())
