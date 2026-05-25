"""Load labelled golden cases for RAG evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

GOLDEN_PATH = Path(__file__).resolve().parent / "golden_set.jsonl"


@dataclass(frozen=True)
class GoldenCase:
    id: str
    query: str
    doc_id: str
    source_pdf: str
    relevant_pages: list[int]
    reference_answer: str
    key_phrases: list[str]


def load_golden_cases(path: Path | None = None) -> list[GoldenCase]:
    path = path or GOLDEN_PATH
    cases: list[GoldenCase] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            cases.append(
                GoldenCase(
                    id=row["id"],
                    query=row["query"],
                    doc_id=row["doc_id"],
                    source_pdf=row["source_pdf"],
                    relevant_pages=[int(p) for p in row["relevant_pages"]],
                    reference_answer=row["reference_answer"],
                    key_phrases=list(row.get("key_phrases", [])),
                )
            )
    return cases
