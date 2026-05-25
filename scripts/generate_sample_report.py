"""
Generate data/raw/sample_report.pdf for Phase 1 demo testing.

Usage:
    python scripts/generate_sample_report.py
"""

from __future__ import annotations

import io
from pathlib import Path

import fitz  # PyMuPDF


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "raw" / "sample_report.pdf"

MARGIN = 54
PAGE_W, PAGE_H = fitz.paper_size("letter")


def _chart_png() -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    quarters = ["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024", "Q1 2025"]
    revenue_m = [42.1, 45.8, 49.2, 54.6, 58.3]

    fig, ax = plt.subplots(figsize=(6.5, 3.2), dpi=150)
    ax.plot(quarters, revenue_m, marker="o", color="#2563eb", linewidth=2.5)
    ax.fill_between(range(len(quarters)), revenue_m, alpha=0.12, color="#2563eb")
    ax.set_title("Figure 3: Quarterly Revenue Trend ($M)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Revenue ($M)")
    ax.set_ylim(35, 65)
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)
    plt.xticks(rotation=20, ha="right")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _add_paragraph(page: fitz.Page, y: float, text: str, fontsize: float = 11) -> float:
    rect = fitz.Rect(MARGIN, y, PAGE_W - MARGIN, PAGE_H - MARGIN)
    remaining = page.insert_textbox(
        rect,
        text,
        fontsize=fontsize,
        fontname="helv",
        align=fitz.TEXT_ALIGN_LEFT,
    )
    used = rect.height - remaining
    return y + used + 14


def _add_heading(page: fitz.Page, y: float, text: str) -> float:
    page.insert_text((MARGIN, y + 16), text, fontsize=16, fontname="helv")
    return y + 34


def _add_table(
    page: fitz.Page,
    y: float,
    headers: list[str],
    rows: list[list[str]],
    col_widths: list[float],
    row_height: float = 22,
) -> float:
    """Draw a ruled table so pdfplumber can detect it via line intersections."""
    x0 = MARGIN
    all_rows = [headers, *rows]
    table_width = sum(col_widths)
    table_height = len(all_rows) * row_height

    for row_idx in range(len(all_rows) + 1):
        line_y = y + row_idx * row_height
        page.draw_line(fitz.Point(x0, line_y), fitz.Point(x0 + table_width, line_y), width=0.6)

    x = x0
    for width in col_widths:
        page.draw_line(fitz.Point(x, y), fitz.Point(x, y + table_height), width=0.6)
        x += width
    page.draw_line(fitz.Point(x0 + table_width, y), fitz.Point(x0 + table_width, y + table_height), width=0.6)

    for row_idx, row in enumerate(all_rows):
        cell_y = y + row_idx * row_height + 15
        cell_x = x0
        for col_idx, cell in enumerate(row):
            page.insert_text(
                (cell_x + 4, cell_y),
                cell,
                fontsize=10,
                fontname="helv",
            )
            cell_x += col_widths[col_idx]

    return y + table_height + 18


def build_pdf() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    chart = _chart_png()

    # --- Page 1: Executive summary ---
    p1 = doc.new_page(width=PAGE_W, height=PAGE_H)
    y = 40
    y = _add_heading(p1, y, "Acme Corp — Annual Performance Report 2024")
    y = _add_paragraph(
        p1,
        y,
        "Executive Summary. Acme Corp delivered strong financial performance in fiscal year 2024, "
        "with total revenue reaching $191.7M, representing 18.4% year-over-year growth. Operating "
        "margin expanded to 22.1% as the company scaled its enterprise SaaS platform and reduced "
        "customer acquisition costs across North America and EMEA.",
    )
    y = _add_paragraph(
        p1,
        y,
        "Revenue growth was driven primarily by expansion within existing accounts and the launch of "
        "the Analytics Pro tier in Q2. Net revenue retention finished the year at 118%, while new "
        "logo acquisition added 340 customers in the mid-market segment.",
    )
    y = _add_heading(p1, y, "Key Highlights")
    y = _add_paragraph(
        p1,
        y,
        "• Total revenue: $191.7M (+18.4% YoY)\n"
        "• Gross margin: 74.2% (+1.8 pts)\n"
        "• Free cash flow: $28.4M\n"
        "• Headcount: 1,240 employees (+12%)\n"
        "• Enterprise customers (> $100K ARR): 186 (+24%)",
    )

    # --- Page 2: Figure + narrative ---
    p2 = doc.new_page(width=PAGE_W, height=PAGE_H)
    y = 40
    y = _add_heading(p2, y, "Revenue Analysis")
    y = _add_paragraph(
        p2,
        y,
        "Figure 3 below shows quarterly revenue from Q1 2024 through Q1 2025. The chart illustrates "
        "a consistent upward trend, with the steepest quarter-over-quarter increase occurring in Q4 "
        "2024 when several large enterprise contracts closed ahead of schedule.",
    )

    chart_rect = fitz.Rect(MARGIN, y, PAGE_W - MARGIN, y + 200)
    p2.insert_image(chart_rect, stream=chart)
    y = chart_rect.y1 + 18

    y = _add_paragraph(
        p2,
        y,
        "Figure 3: Quarterly Revenue Trend ($M). Revenue rose from $42.1M in Q1 2024 to $58.3M in "
        "Q1 2025. Management attributes Q4 strength to seasonal budget flush and a 14% uplift from "
        "Analytics Pro upsells. The Q1 2025 figure includes $3.2M from the newly acquired DataPulse unit.",
    )
    y = _add_paragraph(
        p2,
        y,
        "Looking ahead, the finance team projects full-year 2025 revenue of $230–240M, assuming "
        "continued NRR above 115% and successful rollout of the AI Insights module in H2.",
    )

    # --- Page 3: Ruled table (pdfplumber) + narrative ---
    p3 = doc.new_page(width=PAGE_W, height=PAGE_H)
    y = 40
    y = _add_heading(p3, y, "Quarterly Revenue Detail")
    y = _add_paragraph(
        p3,
        y,
        "Table 1 summarizes quarterly revenue, year-over-year growth, and operating margin for each "
        "period. All figures are in millions of USD unless otherwise noted.",
    )
    y = _add_table(
        p3,
        y,
        headers=["Quarter", "Revenue ($M)", "YoY Growth", "Op. Margin"],
        rows=[
            ["Q1 2024", "42.1", "12.3%", "19.8%"],
            ["Q2 2024", "45.8", "14.1%", "20.5%"],
            ["Q3 2024", "49.2", "15.7%", "21.2%"],
            ["Q4 2024", "54.6", "17.9%", "22.8%"],
            ["Q1 2025", "58.3", "18.5%", "23.1%"],
        ],
        col_widths=[100, 100, 100, 100],
    )
    y = _add_paragraph(
        p3,
        y,
        "The table confirms accelerating growth through the second half of 2024. Operating margin "
        "improved each quarter as infrastructure costs were amortised over a larger customer base. "
        "Q1 2025 margin of 23.1% exceeded the board target of 22.5%.",
    )
    y = _add_paragraph(
        p3,
        y,
        "Risk factors include potential macroeconomic slowdown in EMEA and increased competition in "
        "the analytics segment. Mitigation strategies focus on multi-year contract incentives and "
        "deeper integration with existing CRM and ERP platforms.",
    )

    doc.save(OUTPUT)
    doc.close()
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    build_pdf()
