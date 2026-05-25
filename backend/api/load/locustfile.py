"""Locust load scenario for the RAG API."""

from __future__ import annotations

import os

from locust import HttpUser, between, task

DOC_ID = os.getenv("SAMPLE_DOC_ID", "ed7d53f9b08caa39")


class RAGUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def query_retrieve_only(self) -> None:
        self.client.post(
            "/query",
            json={
                "query": "What was Q4 revenue?",
                "doc_id": DOC_ID,
                "retrieve_only": True,
            },
            name="/query retrieve-only",
        )

    @task(1)
    def health(self) -> None:
        self.client.get("/health", name="/health")
