"""Track folder bulk-ingest progress in Redis (UI polling)."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from shared.config import get_settings

JOB_PREFIX = "bulk_ingest:job:"
JOB_TTL_SECONDS = 86400 * 7


@dataclass
class BulkJobStatus:
    job_id: str
    folder_name: str
    status: str  # uploading | queued | running | done | error
    total: int
    uploaded: int = 0
    processed: int = 0
    ingested: int = 0
    skipped: int = 0
    failed: int = 0
    current_file: str | None = None
    message: str | None = None
    paths: list[str] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def done(self) -> bool:
        return self.status in {"done", "error"}

    def completed_paths(self) -> set[str]:
        return {r["path"] for r in self.results if r.get("path")}

    def pending_paths(self) -> list[str]:
        done = self.completed_paths()
        return [p for p in self.paths if p not in done]

    @property
    def unique_processed(self) -> int:
        return len(self.completed_paths())


class BulkJobStore:
    def __init__(self, redis_url: str | None = None) -> None:
        settings = get_settings()
        self.redis_url = redis_url or settings.redis_url
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import redis

            self._client = redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    def _key(self, job_id: str) -> str:
        return f"{JOB_PREFIX}{job_id}"

    def create(self, job_id: str, *, folder_name: str, total: int) -> BulkJobStatus:
        job = BulkJobStatus(job_id=job_id, folder_name=folder_name, status="uploading", total=total)
        self._save(job)
        return job

    def get(self, job_id: str) -> BulkJobStatus | None:
        raw = self.client.get(self._key(job_id))
        if not raw:
            return None
        data = json.loads(raw)
        return BulkJobStatus(**data)

    def add_uploaded_path(self, job_id: str, path: str, filename: str) -> BulkJobStatus:
        job = self._require(job_id)
        if path not in job.paths:
            job.paths.append(path)
        job.uploaded = len(job.paths)
        job.current_file = filename
        job.updated_at = time.time()
        self._save(job)
        return job

    def mark_queued(self, job_id: str, *, message: str | None = None) -> BulkJobStatus:
        job = self._require(job_id)
        job.status = "queued"
        job.message = message or "Queued for Celery worker"
        job.updated_at = time.time()
        self._save(job)
        return job

    def mark_running(self, job_id: str) -> BulkJobStatus:
        job = self._require(job_id)
        job.status = "running"
        job.message = "Processing with Redis cache"
        job.updated_at = time.time()
        self._save(job)
        return job

    def record_task_result(self, job_id: str, result: dict[str, Any]) -> BulkJobStatus:
        job = self._require(job_id)
        path = result.get("path")
        if path:
            job.results = [r for r in job.results if r.get("path") != path]
        job.results.append(result)
        job.current_file = path or job.current_file
        self._recompute_progress(job)
        job.updated_at = time.time()
        self._save(job)
        return job

    def _recompute_progress(self, job: BulkJobStatus) -> None:
        """Derive counters from unique path results (safe for retries / resume duplicates)."""
        job.ingested = 0
        job.skipped = 0
        job.failed = 0
        for entry in job.results:
            status = entry.get("status")
            if status == "skipped":
                job.skipped += 1
            elif status == "success":
                if entry.get("errors") and entry.get("chunk_count", 0) == 0:
                    job.failed += 1
                else:
                    job.ingested += 1
            else:
                job.failed += 1

        job.processed = job.unique_processed
        expected = len(job.paths) if job.paths else job.total
        if expected > 0 and job.processed >= expected:
            job.status = "done"
            job.message = f"{job.ingested} ingested · {job.skipped} skipped · {job.failed} failed"
            job.current_file = None
        elif job.status not in {"done", "error"} and job.processed > 0:
            job.status = "running"

    def mark_error(self, job_id: str, message: str) -> BulkJobStatus:
        job = self._require(job_id)
        job.status = "error"
        job.message = message
        job.updated_at = time.time()
        self._save(job)
        return job

    def _require(self, job_id: str) -> BulkJobStatus:
        job = self.get(job_id)
        if job is None:
            raise KeyError(f"Unknown bulk job: {job_id}")
        return job

    def _save(self, job: BulkJobStatus) -> None:
        self.client.setex(self._key(job.job_id), JOB_TTL_SECONDS, json.dumps(asdict(job)))
