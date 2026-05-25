"""
Generate a folder of unique PDFs for Phase 3 bulk-ingest testing.

Usage (Docker — preferred):
    cd docker
    docker compose exec ingest-worker python scripts/generate_bulk_pdfs.py --count 100

Usage (host):
    python scripts/generate_bulk_pdfs.py --count 100
"""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "raw" / "bulk"

MARGIN = 54
PAGE_W, PAGE_H = fitz.paper_size("letter")

SECTORS = (
    "enterprise SaaS",
    "healthcare analytics",
    "fintech payments",
    "industrial IoT",
    "cybersecurity",
    "HR technology",
    "supply chain",
    "climate tech",
    "edtech platforms",
    "legal automation",
)


def _add_text(page: fitz.Page, y: float, text: str, *, fontsize: float = 11) -> float:
    rect = fitz.Rect(MARGIN, y, PAGE_W - MARGIN, PAGE_H - MARGIN)
    remaining = page.insert_textbox(rect, text, fontsize=fontsize, fontname="helv")
    used = rect.height - remaining
    return y + used + 12


def _build_one(index: int) -> fitz.Document:
    """Single-page PDF with unique financial narrative (fast text-only ingest)."""
    company = f"Company {index:03d}"
    sector = SECTORS[index % len(SECTORS)]
    revenue = 50.0 + index * 1.37
    growth = 8.0 + (index % 17) * 0.6
    margin = 14.0 + (index % 11) * 0.5
    nrr = 102 + (index % 20)
    customers = 120 + index * 3
    year = 2020 + (index % 5)

    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    y = 40
    page.insert_text((MARGIN, y + 18), f"{company} — Annual Report {year}", fontsize=16, fontname="helv")
    y += 40

    body = (
        f"Executive Summary. {company} operates in {sector} and reported fiscal year {year} "
        f"revenue of ${revenue:.1f}M, representing {growth:.1f}% year-over-year growth. "
        f"Operating margin reached {margin:.1f}% as the company scaled its platform across "
        f"North America, EMEA, and APAC regions.\n\n"
        f"Net revenue retention finished at {nrr}%. The customer base grew to {customers} "
        f"active accounts, with expansion revenue contributing more than new-logo ARR in "
        f"the second half of the year. Product investments focused on AI-assisted workflows "
        f"and deeper integrations with ERP and CRM systems.\n\n"
        f"Document ID: bulk-report-{index:04d}. This synthetic report is generated for "
        f"Phase 3 scalable ingestion testing. Each file has a unique filename and content "
        f"so Qdrant receives distinct doc_id values during bulk ingest benchmarks."
    )
    _add_text(page, y, body)
    return doc


def generate_bulk_pdfs(count: int, output_dir: Path, *, force: bool = False) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for i in range(count):
        path = output_dir / f"report_{i:04d}.pdf"
        if path.exists() and not force:
            written.append(path)
            continue
        doc = _build_one(i)
        doc.save(path)
        doc.close()
        written.append(path)

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate bulk test PDFs")
    parser.add_argument("--count", type=int, default=100, help="Number of PDFs to create")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output directory")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    paths = generate_bulk_pdfs(args.count, args.output, force=args.force)
    total_kb = sum(p.stat().st_size for p in paths) // 1024
    print(f"Wrote {len(paths)} PDFs to {args.output} ({total_kb} KB total)")
    print(f"Example: {paths[0].relative_to(ROOT)}")


if __name__ == "__main__":
    main()
