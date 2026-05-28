"""Generate ``docs/documind-book.pdf`` — a long-form reference book describing
what the DocuMind repository is and how every layer works.

The output is byte-reproducible: re-running this script on the same source
tree produces an identical PDF (see ``SOURCE_DATE_EPOCH``).

Run from the repo root::

    python scripts/generate_book.py

Dependencies: ``pymupdf`` (already a hard dependency of the backend).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import fitz

OUTPUT_PATH = Path("docs/documind-book.pdf")

# ---- Page geometry (A4, 72 DPI) -------------------------------------------------
PAGE_W, PAGE_H = 595.28, 841.89
MARGIN_L = 72
MARGIN_R = 72
MARGIN_T = 90
MARGIN_B = 90
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R
CONTENT_H = PAGE_H - MARGIN_T - MARGIN_B

# ---- Fonts (PyMuPDF built-ins, no external files) -----------------------------
F_BODY = "helv"
F_BOLD = "hebo"
F_ITAL = "heit"
F_MONO = "cour"
F_MONO_BOLD = "cobo"

# ---- Sizes / colors -----------------------------------------------------------
S_BODY = 10.5
S_BODY_SMALL = 9
S_CODE = 9
S_H2 = 16
S_H3 = 12
LH_BODY = 14
LH_CODE = 11.5

C_TEXT = (0.10, 0.10, 0.15)
C_TEXT_SOFT = (0.30, 0.30, 0.40)
C_TEXT_MUTED = (0.50, 0.50, 0.60)
C_ACCENT = (0.34, 0.27, 0.61)        # deep purple
C_ACCENT_LIGHT = (0.62, 0.55, 0.86)
C_CODE_BG = (0.96, 0.97, 1.00)
C_CODE_BORDER = (0.85, 0.87, 0.95)
C_CODE_BAR = (0.40, 0.50, 0.80)
C_RULE = (0.90, 0.90, 0.95)
C_NOTE_BG = (1.00, 0.97, 0.91)
C_NOTE_BORDER = (0.90, 0.70, 0.40)
C_NOTE_LABEL = (0.60, 0.40, 0.00)


def _epoch_to_datetime() -> datetime:
    """Pin every timestamp leak so the PDF is byte-reproducible."""
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "1704067200"))
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def _pdf_date(ts: datetime) -> str:
    return ts.strftime("D:%Y%m%d%H%M%S+00'00'")


class BookBuilder:
    def __init__(self) -> None:
        self.doc = fitz.open()
        self.page: fitz.Page | None = None
        self.y = MARGIN_T
        self.toc_entries: list[tuple[int, str, int]] = []  # (level, title, 1-indexed page)
        self.current_chapter_title = "DocuMind"
        self.chapter_count = 0
        self.toc_start_idx: int | None = None
        self.toc_reserved = 0
        self._page_chapter: list[str] = []  # chapter title indexed by page index

    # ----- low-level helpers --------------------------------------------------

    def _new_page(self) -> None:
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.y = MARGIN_T
        self._page_chapter.append(self.current_chapter_title)

    def _ensure(self, h: float) -> None:
        if self.y + h > PAGE_H - MARGIN_B:
            self._new_page()

    def _wrap(self, text: str, width: float, font: str, size: float) -> list[str]:
        out: list[str] = []
        for paragraph in text.split("\n"):
            words = paragraph.split(" ")
            cur = ""
            for w in words:
                trial = w if not cur else cur + " " + w
                if fitz.get_text_length(trial, fontname=font, fontsize=size) <= width:
                    cur = trial
                else:
                    if cur:
                        out.append(cur)
                    # word longer than width — hard break
                    while fitz.get_text_length(w, fontname=font, fontsize=size) > width:
                        # find largest prefix that fits
                        lo, hi = 1, len(w)
                        while lo < hi:
                            mid = (lo + hi + 1) // 2
                            if fitz.get_text_length(w[:mid], fontname=font, fontsize=size) <= width:
                                lo = mid
                            else:
                                hi = mid - 1
                        out.append(w[:lo])
                        w = w[lo:]
                    cur = w
            if cur:
                out.append(cur)
        return out

    # ----- high-level layout primitives ---------------------------------------

    def cover(self, title: str, subtitle: str, author: str, version: str) -> None:
        self._new_page()
        # decorative band at top
        self.page.draw_rect(
            fitz.Rect(0, 0, PAGE_W, 6), fill=C_ACCENT, color=None,
        )
        self.page.draw_rect(
            fitz.Rect(0, PAGE_H - 6, PAGE_W, PAGE_H), fill=C_ACCENT, color=None,
        )

        cy = PAGE_H / 2 - 100
        # eyebrow label
        eyebrow = "THE COMPLETE REFERENCE"
        w = fitz.get_text_length(eyebrow, fontname=F_BOLD, fontsize=10)
        self.page.insert_text(
            ((PAGE_W - w) / 2, cy), eyebrow,
            fontname=F_BOLD, fontsize=10, color=C_ACCENT,
        )
        cy += 32

        # title
        title_size = 38
        w = fitz.get_text_length(title, fontname=F_BOLD, fontsize=title_size)
        self.page.insert_text(
            ((PAGE_W - w) / 2, cy), title,
            fontname=F_BOLD, fontsize=title_size, color=C_TEXT,
        )
        cy += 48

        # subtitle (wrap if needed, centered)
        for line in self._wrap(subtitle, CONTENT_W - 60, F_ITAL, 14):
            w = fitz.get_text_length(line, fontname=F_ITAL, fontsize=14)
            self.page.insert_text(
                ((PAGE_W - w) / 2, cy), line,
                fontname=F_ITAL, fontsize=14, color=C_TEXT_SOFT,
            )
            cy += 20
        cy += 24

        # divider
        self.page.draw_line(
            (PAGE_W * 0.32, cy), (PAGE_W * 0.68, cy),
            color=C_ACCENT_LIGHT, width=1.5,
        )
        cy += 32

        # version
        version_line = f"Version {version}"
        w = fitz.get_text_length(version_line, fontname=F_BODY, fontsize=11)
        self.page.insert_text(
            ((PAGE_W - w) / 2, cy), version_line,
            fontname=F_BODY, fontsize=11, color=C_TEXT_MUTED,
        )

        # author / date at bottom
        ts = _epoch_to_datetime()
        date_str = ts.strftime("%B %Y")
        footer = f"{author}   ·   {date_str}"
        w = fitz.get_text_length(footer, fontname=F_BODY, fontsize=11)
        self.page.insert_text(
            ((PAGE_W - w) / 2, PAGE_H - 110), footer,
            fontname=F_BODY, fontsize=11, color=C_TEXT_MUTED,
        )

    def front_page(self, title: str) -> None:
        self._new_page()
        self.current_chapter_title = title
        self.y = MARGIN_T + 40
        self.page.insert_text(
            (MARGIN_L, self.y), title,
            fontname=F_BOLD, fontsize=26, color=C_TEXT,
        )
        self.y += 12
        self.page.draw_line(
            (MARGIN_L, self.y + 10), (MARGIN_L + 80, self.y + 10),
            color=C_ACCENT, width=2,
        )
        self.y += 38

    def chapter(self, title: str) -> None:
        self._new_page()
        self.current_chapter_title = title
        self.chapter_count += 1
        self.toc_entries.append((1, title, len(self.doc)))
        self._draw_chapter_header(f"CHAPTER {self.chapter_count}", title)

    def appendix(self, title: str) -> None:
        """Same visual treatment as `chapter` but labelled APPENDIX and
        recorded under a separate level so the TOC skips the chapter number."""
        self._new_page()
        self.current_chapter_title = title
        # level=0 indicates "appendix" — TOC renderer treats it like a top-level
        # entry but without a numeric prefix.
        self.toc_entries.append((0, title, len(self.doc)))
        self._draw_chapter_header("APPENDIX", title)

    def _draw_chapter_header(self, eyebrow: str, title: str) -> None:
        self.y = MARGIN_T + 80
        self.page.insert_text(
            (MARGIN_L, self.y), eyebrow,
            fontname=F_BOLD, fontsize=10, color=C_ACCENT,
        )
        self.y += 26
        for line in self._wrap(title, CONTENT_W, F_BOLD, 28):
            self.page.insert_text(
                (MARGIN_L, self.y), line,
                fontname=F_BOLD, fontsize=28, color=C_TEXT,
            )
            self.y += 34
        self.y += 6
        self.page.draw_line(
            (MARGIN_L, self.y), (MARGIN_L + 100, self.y),
            color=C_ACCENT, width=2,
        )
        self.y += 32

    def section(self, title: str) -> None:
        self._ensure(40)
        self.toc_entries.append((2, title, len(self.doc)))
        self.y += 14
        for line in self._wrap(title, CONTENT_W, F_BOLD, S_H2):
            self._ensure(24)
            self.page.insert_text(
                (MARGIN_L, self.y + S_H2), line,
                fontname=F_BOLD, fontsize=S_H2, color=C_TEXT,
            )
            self.y += 22
        self.y += 8

    def subsection(self, title: str) -> None:
        self._ensure(28)
        self.y += 6
        for line in self._wrap(title, CONTENT_W, F_BOLD, S_H3):
            self._ensure(18)
            self.page.insert_text(
                (MARGIN_L, self.y + S_H3), line,
                fontname=F_BOLD, fontsize=S_H3, color=C_TEXT_SOFT,
            )
            self.y += 16
        self.y += 4

    def para(self, text: str) -> None:
        lines = self._wrap(text.strip(), CONTENT_W, F_BODY, S_BODY)
        for ln in lines:
            self._ensure(LH_BODY)
            self.page.insert_text(
                (MARGIN_L, self.y + S_BODY), ln,
                fontname=F_BODY, fontsize=S_BODY, color=C_TEXT,
            )
            self.y += LH_BODY
        self.y += 4

    def bullets(self, items: list[str]) -> None:
        for item in items:
            lines = self._wrap(item, CONTENT_W - 18, F_BODY, S_BODY)
            for i, ln in enumerate(lines):
                self._ensure(LH_BODY)
                if i == 0:
                    self.page.insert_text(
                        (MARGIN_L + 4, self.y + S_BODY), "\u2022",
                        fontname=F_BOLD, fontsize=S_BODY, color=C_ACCENT,
                    )
                self.page.insert_text(
                    (MARGIN_L + 18, self.y + S_BODY), ln,
                    fontname=F_BODY, fontsize=S_BODY, color=C_TEXT,
                )
                self.y += LH_BODY
        self.y += 4

    def numbered(self, items: list[str]) -> None:
        for i, item in enumerate(items, 1):
            label = f"{i}."
            lines = self._wrap(item, CONTENT_W - 22, F_BODY, S_BODY)
            for j, ln in enumerate(lines):
                self._ensure(LH_BODY)
                if j == 0:
                    self.page.insert_text(
                        (MARGIN_L, self.y + S_BODY), label,
                        fontname=F_BOLD, fontsize=S_BODY, color=C_ACCENT,
                    )
                self.page.insert_text(
                    (MARGIN_L + 22, self.y + S_BODY), ln,
                    fontname=F_BODY, fontsize=S_BODY, color=C_TEXT,
                )
                self.y += LH_BODY
        self.y += 4

    def code(self, text: str) -> None:
        raw_lines = text.rstrip("\n").split("\n")
        # wrap each code line at CONTENT_W (preserve indentation)
        wrapped: list[str] = []
        for ln in raw_lines:
            if fitz.get_text_length(ln, fontname=F_MONO, fontsize=S_CODE) <= CONTENT_W - 16:
                wrapped.append(ln)
            else:
                # crude wrap on width
                cur = ""
                for ch in ln:
                    if fitz.get_text_length(cur + ch, fontname=F_MONO, fontsize=S_CODE) <= CONTENT_W - 16:
                        cur += ch
                    else:
                        wrapped.append(cur)
                        cur = "  " + ch  # continuation indent
                if cur:
                    wrapped.append(cur)
        # paginate the code block by chunks
        i = 0
        while i < len(wrapped):
            available = PAGE_H - MARGIN_B - self.y - 14
            if available < LH_CODE * 3:
                self._new_page()
                available = PAGE_H - MARGIN_B - self.y - 14
            n_fit = max(1, int(available // LH_CODE))
            chunk = wrapped[i : i + n_fit]
            h = len(chunk) * LH_CODE + 12
            rect = fitz.Rect(
                MARGIN_L - 6, self.y, MARGIN_L + CONTENT_W + 6, self.y + h
            )
            self.page.draw_rect(
                rect, fill=C_CODE_BG, color=C_CODE_BORDER, width=0.5,
            )
            self.page.draw_rect(
                fitz.Rect(MARGIN_L - 6, self.y, MARGIN_L - 3, self.y + h),
                fill=C_CODE_BAR, color=None,
            )
            cy = self.y + 6
            for ln in chunk:
                self.page.insert_text(
                    (MARGIN_L, cy + S_CODE), ln,
                    fontname=F_MONO, fontsize=S_CODE, color=(0.05, 0.05, 0.20),
                )
                cy += LH_CODE
            self.y += h + 4
            i += n_fit

    def note(self, label: str, text: str) -> None:
        lines = self._wrap(text, CONTENT_W - 28, F_BODY, S_BODY)
        h = len(lines) * LH_BODY + 22
        if self.y + h > PAGE_H - MARGIN_B:
            self._new_page()
        rect = fitz.Rect(MARGIN_L, self.y, MARGIN_L + CONTENT_W, self.y + h)
        self.page.draw_rect(rect, fill=C_NOTE_BG, color=C_NOTE_BORDER, width=0.5)
        cy = self.y + 6
        self.page.insert_text(
            (MARGIN_L + 12, cy + S_BODY), label.upper(),
            fontname=F_BOLD, fontsize=S_BODY_SMALL, color=C_NOTE_LABEL,
        )
        cy += LH_BODY
        for ln in lines:
            self.page.insert_text(
                (MARGIN_L + 12, cy + S_BODY), ln,
                fontname=F_BODY, fontsize=S_BODY, color=C_TEXT,
            )
            cy += LH_BODY
        self.y += h + 4

    def kv_table(self, rows: list[tuple[str, str]]) -> None:
        col1 = CONTENT_W * 0.30
        col2 = CONTENT_W - col1
        self.y += 2
        self.page.draw_line(
            (MARGIN_L, self.y), (MARGIN_L + CONTENT_W, self.y),
            color=C_RULE, width=0.5,
        )
        for k, v in rows:
            k_lines = self._wrap(k, col1 - 8, F_MONO_BOLD, S_BODY_SMALL)
            v_lines = self._wrap(v, col2 - 8, F_BODY, S_BODY_SMALL)
            n = max(len(k_lines), len(v_lines))
            h = n * 12 + 4
            if self.y + h > PAGE_H - MARGIN_B:
                self._new_page()
                self.page.draw_line(
                    (MARGIN_L, self.y), (MARGIN_L + CONTENT_W, self.y),
                    color=C_RULE, width=0.5,
                )
            cy = self.y + 3
            for i in range(n):
                if i < len(k_lines):
                    self.page.insert_text(
                        (MARGIN_L + 4, cy + S_BODY_SMALL), k_lines[i],
                        fontname=F_MONO_BOLD, fontsize=S_BODY_SMALL, color=C_ACCENT,
                    )
                if i < len(v_lines):
                    self.page.insert_text(
                        (MARGIN_L + col1 + 4, cy + S_BODY_SMALL), v_lines[i],
                        fontname=F_BODY, fontsize=S_BODY_SMALL, color=C_TEXT,
                    )
                cy += 12
            self.y += h
            self.page.draw_line(
                (MARGIN_L, self.y), (MARGIN_L + CONTENT_W, self.y),
                color=C_RULE, width=0.4,
            )
        self.y += 8

    # ----- TOC handling -------------------------------------------------------

    def reserve_toc(self, n_pages: int) -> None:
        self.current_chapter_title = "Contents"
        self.toc_start_idx = len(self.doc)
        for _ in range(n_pages):
            self.doc.new_page(width=PAGE_W, height=PAGE_H)
            self._page_chapter.append("Contents")
        self.toc_reserved = n_pages

    def render_toc(self) -> None:
        if self.toc_start_idx is None:
            return
        ptr = self.toc_start_idx
        page = self.doc[ptr]
        y = MARGIN_T + 40
        page.insert_text(
            (MARGIN_L, y), "Table of Contents",
            fontname=F_BOLD, fontsize=26, color=C_TEXT,
        )
        y += 12
        page.draw_line(
            (MARGIN_L, y + 10), (MARGIN_L + 100, y + 10),
            color=C_ACCENT, width=2,
        )
        y += 36

        def maybe_advance() -> None:
            nonlocal ptr, page, y
            if y + 18 > PAGE_H - MARGIN_B:
                ptr += 1
                if ptr >= self.toc_start_idx + self.toc_reserved:
                    # If we underestimated, append a new TOC page at the end
                    # (page numbers below will be off by however many we added).
                    page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
                    self._page_chapter.append("Contents")
                    self.toc_reserved += 1
                else:
                    page = self.doc[ptr]
                y = MARGIN_T

        ch_num = 0
        for level, title, page_num in self.toc_entries:
            maybe_advance()
            if level in (0, 1):
                if level == 1:
                    ch_num += 1
                    left = f"{ch_num}.  {title}"
                else:
                    left = title
                left_lines = self._wrap(left, CONTENT_W * 0.78, F_BOLD, 12)
                for i, ln in enumerate(left_lines):
                    if i == len(left_lines) - 1:
                        page.insert_text(
                            (MARGIN_L, y + 12), ln,
                            fontname=F_BOLD, fontsize=12, color=C_TEXT,
                        )
                        pn_s = str(page_num)
                        pn_w = fitz.get_text_length(pn_s, fontname=F_BOLD, fontsize=12)
                        page.insert_text(
                            (MARGIN_L + CONTENT_W - pn_w, y + 12), pn_s,
                            fontname=F_BOLD, fontsize=12, color=C_TEXT,
                        )
                    else:
                        page.insert_text(
                            (MARGIN_L, y + 12), ln,
                            fontname=F_BOLD, fontsize=12, color=C_TEXT,
                        )
                    y += 18
                y += 2
            else:
                left = title
                left_lines = self._wrap(left, CONTENT_W * 0.74, F_BODY, 10)
                for i, ln in enumerate(left_lines):
                    maybe_advance()
                    if i == len(left_lines) - 1:
                        page.insert_text(
                            (MARGIN_L + 24, y + 10), ln,
                            fontname=F_BODY, fontsize=10, color=C_TEXT_SOFT,
                        )
                        pn_s = str(page_num)
                        pn_w = fitz.get_text_length(pn_s, fontname=F_BODY, fontsize=10)
                        page.insert_text(
                            (MARGIN_L + CONTENT_W - pn_w, y + 10), pn_s,
                            fontname=F_BODY, fontsize=10, color=C_TEXT_SOFT,
                        )
                    else:
                        page.insert_text(
                            (MARGIN_L + 24, y + 10), ln,
                            fontname=F_BODY, fontsize=10, color=C_TEXT_SOFT,
                        )
                    y += 14

    # ----- finalize -----------------------------------------------------------

    def finalize(self) -> None:
        n_pages = len(self.doc)
        # Pad page_chapter list if TOC was reserved late.
        while len(self._page_chapter) < n_pages:
            self._page_chapter.append("DocuMind")

        for i in range(n_pages):
            page = self.doc[i]
            if i == 0:
                continue  # cover
            chap = self._page_chapter[i] if i < len(self._page_chapter) else "DocuMind"
            # header rule
            page.draw_line(
                (MARGIN_L, MARGIN_T - 14),
                (MARGIN_L + CONTENT_W, MARGIN_T - 14),
                color=C_RULE, width=0.5,
            )
            # left header: book title
            page.insert_text(
                (MARGIN_L, MARGIN_T - 20), "DocuMind — The Complete Reference",
                fontname=F_BODY, fontsize=8, color=C_TEXT_MUTED,
            )
            # right header: chapter title
            w = fitz.get_text_length(chap, fontname=F_ITAL, fontsize=8)
            page.insert_text(
                (MARGIN_L + CONTENT_W - w, MARGIN_T - 20), chap,
                fontname=F_ITAL, fontsize=8, color=C_TEXT_MUTED,
            )
            # footer page number
            pn = str(i + 1)
            w = fitz.get_text_length(pn, fontname=F_BODY, fontsize=9)
            page.insert_text(
                ((PAGE_W - w) / 2, PAGE_H - 50), pn,
                fontname=F_BODY, fontsize=9, color=C_TEXT_MUTED,
            )

        # PDF outline / bookmarks: appendices (level=0) become top-level
        # entries in the outline (PyMuPDF wants level >= 1).
        outline = [
            [max(1, level), title, page]
            for level, title, page in self.toc_entries
        ]
        self.doc.set_toc(outline)

        ts = _epoch_to_datetime()
        pdf_date = _pdf_date(ts)
        self.doc.set_metadata({
            "title": "DocuMind — The Complete Reference",
            "subject": "Architecture, ingest pipeline, retrieval, evaluation, and deployment of the DocuMind multimodal RAG system.",
            "author": "DocuMind contributors",
            "keywords": "RAG, retrieval-augmented generation, multimodal, qdrant, FastAPI, BGE-M3, CLIP, ColPali",
            "creator": "scripts/generate_book.py (PyMuPDF)",
            "producer": "PyMuPDF",
            "creationDate": pdf_date,
            "modDate": pdf_date,
        })

    def save(self, path: Path) -> None:
        self.finalize()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(path), no_new_id=True, deflate=True, garbage=4)


# =============================================================================
# Content
# =============================================================================


def build_book() -> BookBuilder:
    b = BookBuilder()

    b.cover(
        title="DocuMind",
        subtitle="The Complete Reference — production-grade multimodal RAG over PDFs, end to end",
        author="DocuMind contributors",
        version="0.1",
    )

    # -------- Copyright / colophon ---------------------------------------------
    b.front_page("Colophon")
    b.para(
        "DocuMind — The Complete Reference describes the architecture, "
        "implementation, and operations of the open-source DocuMind project "
        "(https://github.com/dyh1265/RAG). This book is generated directly "
        "from the repository by the script scripts/generate_book.py and is "
        "byte-reproducible: re-running the script on the same source tree "
        "produces an identical PDF. The wall-clock fields the PDF format "
        "demands are pinned via SOURCE_DATE_EPOCH."
    )
    b.para(
        "Code excerpts in this book reference the master branch at the time "
        "of generation. Cross-references to backend.* and frontend/ paths map "
        "directly to the repository layout described in Appendix A."
    )
    b.para(
        "The book is released under the MIT license, the same terms as the "
        "source repository. You are free to copy, fork, adapt, and ship it."
    )
    b.subsection("Type and layout")
    b.para(
        "Body text is set in Helvetica at 10.5pt with 14pt leading on an A4 "
        "page. Code is set in Courier at 9pt. Headings are Helvetica Bold. "
        "Layout is produced by PyMuPDF (fitz) using the built-in PDF type-1 "
        "fonts; no external font files are required."
    )

    # -------- Preface ---------------------------------------------------------
    b.front_page("Preface")
    b.para(
        "Most RAG repositories are notebooks. They show that the idea works "
        "and stop there. The thing they consistently miss is what makes a "
        "real product: the second day of operation."
    )
    b.para(
        "On the first day you can stitch together a vector store, a chunker, "
        "an embedding model, and a chat completion call, and get an answer. "
        "On the second day the questions arrive: how do you tell whether the "
        "answer is right? how do you keep it right when you change the "
        "chunker? what happens when the PDF has a 14-column table? what does "
        "the user see when the LLM is unreachable? where do PII redactions "
        "happen, and at which stage? what gets cached, and what doesn't? how "
        "do you make ingest of a large folder of PDFs not block the chat UI? "
        "what does the latency budget look like end-to-end, and which knob "
        "buys you the most quality per millisecond?"
    )
    b.para(
        "DocuMind is one answer to that second day. It is not the best "
        "possible answer; it is an opinionated, working one. This book exists "
        "so that, by the time you have read it, those questions and their "
        "trade-offs are visible to you in concrete code paths rather than "
        "vague principles."
    )
    b.subsection("Who this book is for")
    b.bullets([
        "Engineers building a RAG system over structured documents who want to see how the pieces fit before deciding which to keep and which to swap.",
        "Reviewers evaluating the repository for portfolio purposes who want a single document explaining what is here and why.",
        "Operators running DocuMind in production who need a reference for every configuration knob, metric, and failure mode.",
        "Contributors who want to understand the design intent of a module before changing it.",
    ])
    b.subsection("How to read it")
    b.para(
        "The book is structured as a single read-through. Chapters 1 and 2 "
        "give the motivation and the system topology — read them in order. "
        "Chapters 3 through 6 follow a document and a question through the "
        "pipeline, layer by layer; you can read them in order or jump to the "
        "layer you are debugging. Chapters 7 through 10 cover the operational "
        "surface — evaluation, observability, scaling, deployment. Chapters "
        "11 and 12, and the appendices, are reference material: dip into them "
        "when you need an HTTP endpoint or a config flag."
    )
    b.note(
        "convention",
        "Throughout, file paths are written with forward slashes and rooted at the repository, e.g. backend/core/pipeline.py. Environment variable names are in SCREAMING_SNAKE_CASE; Python settings on the Settings class are in snake_case.",
    )

    # Reserve TOC pages — fill last
    b.reserve_toc(3)

    # =========================================================================
    # Chapter 1: What DocuMind is
    # =========================================================================
    b.chapter("What DocuMind Is and Why")

    b.section("The problem")
    b.para(
        "Retrieval-Augmented Generation is the practical answer to the "
        "hardest single failure mode of large language models: they confidently "
        "produce statements they cannot back up. The fix is mechanical — find "
        "passages from a trusted corpus that look relevant to the question, "
        "show them to the model, and require the model to answer only with "
        "what is in those passages, citing them."
    )
    b.para(
        "Once you take that idea seriously the implementation expands quickly. "
        "Where do the passages come from? PDFs from your finance team, slide "
        "decks from product marketing, scientific papers with figures and "
        "tables, scanned forms with no embedded text at all. How do you split "
        "them so the retriever can find the right span without losing context? "
        "How do you handle a question whose answer is in a chart caption, not "
        "the prose? How do you keep retrieval honest after a year of drift in "
        "the underlying corpus? What does the user see when the LLM is down, "
        "when the embedding model OOMs on a large doc, when the answer "
        "violates an internal taxonomy?"
    )
    b.para(
        "DocuMind is a working system that answers all of those questions in "
        "code. It is deliberately not a black-box library you import and "
        "configure; it is a small, opinionated stack of services you can read, "
        "swap, and operate."
    )

    b.section("The shape of the solution")
    b.para(
        "DocuMind ingests PDFs as four kinds of content — text passages, "
        "tables, figures, and, optionally, whole page images — and stores "
        "each kind in its own vector collection. At query time it retrieves "
        "across all of them in parallel, fuses the results with rank-based "
        "reciprocal rank fusion, optionally reranks with a cross-encoder, and "
        "asks an LLM (OpenAI or a local Ollama) to answer with inline "
        "citations that point back to the chunk, page number, and bounding "
        "box. The frontend renders those citations as clickable badges that "
        "open the source page."
    )
    b.para("The stack as it ships:")
    b.bullets([
        "Frontend: React + Vite with a chat UI, document preview, and bulk-upload progress.",
        "API: FastAPI with rate limiting, PII redaction, taxonomy guardrails, OpenTelemetry tracing, and a Server-Sent Events progress stream for long ingests.",
        "Pipeline: a single RAGPipeline class that the API, eval suite, and Celery worker all share.",
        "Ingestion: PyMuPDF + pdfplumber + Tesseract OCR for parsing; BGE-M3 + CLIP + (optional) ColPali for embeddings.",
        "Vector store: Qdrant with four collections — text_chunks, table_chunks, figure_chunks, page_chunks.",
        "Queue and cache: Redis as both the Celery broker and the embedding cache (chunk fingerprint keyed, 7-day TTL).",
        "Workers: Celery for bulk ingest, with LSH dedup against the Qdrant content hash.",
        "Observability: Prometheus, Grafana, Jaeger; an OpenTelemetry collector wires traces through ingest and retrieval.",
        "Evaluation: a hand-curated golden set with CI-gated thresholds for recall@5, hit@5, MRR, p95 retrieval latency, and answer keyword coverage.",
    ])

    b.section("When this design is a good fit")
    b.bullets([
        "Your corpus is structured documents — PDFs with figures, tables, equations, layouts — not just plain prose.",
        "You want citations the user can click through to the source page, not just an answer.",
        "You can tolerate a multi-service stack (Qdrant + Redis + an API and worker) in exchange for proper observability, dedup, and bulk-ingest semantics.",
        "You care about evaluation as a first-class concern, not an afterthought.",
        "You expect to swap individual components (reranker, embedder, LLM) without rewriting the pipeline.",
    ])

    b.section("When something else might be a better fit")
    b.bullets([
        "You have plain-text knowledge-base articles — a single-collection vector index and a small library are probably overkill in reverse here.",
        "You need sub-100 millisecond p95 — the multimodal fusion plus optional reranker stage is honest about its latency budget.",
        "You need streaming token-by-token UX — currently the generator returns the full answer (extending to streaming is straightforward and noted in Chapter 5).",
        "You are working in a heavily regulated context that forbids any LLM call — DocuMind can run retrieve-only, but its main loop assumes a generation step.",
    ])

    b.section("A two-minute tour")
    b.para(
        "The fastest way to internalize the project is to run it. From a clean "
        "checkout on a host with Docker:"
    )
    b.code(
        "cp .env.example .env\n"
        "# put your OPENAI_API_KEY in .env\n"
        "cd docker\n"
        "docker compose --profile production up -d --build"
    )
    b.para(
        "Open http://localhost:8080, drag any PDF onto the upload card, watch "
        "the ingest progress stages (uploading, parsing, chunking, embedding, "
        "indexing), then ask a question. The answer comes back with citation "
        "badges; clicking one opens the source panel and jumps the embedded "
        "PDF viewer to the right page."
    )
    b.note(
        "GPU vs CPU",
        "The default Compose stack runs on CPU. To use an NVIDIA GPU, add the GPU overlay: docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile production up -d --build. This picks the cu124 PyTorch wheels and sets EMBEDDING_DEVICE=cuda. See Chapter 10 for the full deployment guide.",
    )

    # =========================================================================
    # Chapter 2: Architecture
    # =========================================================================
    b.chapter("The Big Picture")

    b.section("Service topology")
    b.para(
        "DocuMind is split into a stateless API layer, a stateful retrieval "
        "layer, a worker tier for bulk ingest, and an observability sidecar. "
        "Each piece is a separate container so they can be scaled or replaced "
        "independently. The diagram below sketches the flow; the next "
        "subsections name every box."
    )
    b.code(
        "Browser --> React/Vite --> nginx --> FastAPI (rag-api)\n"
        "                                       |\n"
        "                                       v\n"
        "                                 RAGPipeline\n"
        "                                 +-- Ingestion --> Qdrant\n"
        "                                 +-- Retrieval  --> Qdrant\n"
        "                                 +-- Taxonomy guard\n"
        "                                 +-- LLM (OpenAI / Ollama)\n"
        "\n"
        "FastAPI ---> Celery worker (Redis broker) --> Qdrant\n"
        "FastAPI ---> OpenTelemetry collector --> Jaeger\n"
        "FastAPI ---> /metrics <-- Prometheus --> Grafana"
    )

    b.section("Components and their responsibilities")
    b.kv_table([
        ("Frontend", "frontend/ — chat UI, citation rendering, document preview, bulk-upload progress. Vite dev or nginx in production."),
        ("API", "backend/api/ — FastAPI routers (query, ingest, bulk_ingest, admin, health), rate limiting (slowapi), PII guardrails, CORS, OpenTelemetry."),
        ("Pipeline", "backend/core/pipeline.py — single RAGPipeline class. The API, eval harness, and Celery worker all run through it instead of wiring components by hand."),
        ("Ingestion", "backend/ingestion/ — PDF text/table/figure parsers, Tesseract OCR, BGE-M3 + CLIP + ColPali embedders, the Qdrant store wrapper."),
        ("Retrieval", "backend/retrieval/ — hybrid BM25 + dense, multimodal RRF fusion, parent-chunk expansion, cross-encoder + FlashRank rerankers, chunk filters."),
        ("Generation", "backend/generation/answer_generator.py — OpenAI + Ollama backends, citation building, fallback when the LLM is unreachable."),
        ("Scaling", "backend/scaling/ — Celery bulk-ingest tasks, Redis embedding cache, fingerprint-based dedup."),
        ("Taxonomy", "backend/taxonomy/ — RDF taxonomy validation, conformity checking, fuzzy entity linking. Can warn or hard-block forbidden answers."),
        ("Vector DB", "Qdrant — four collections: text_chunks, table_chunks, figure_chunks, page_chunks (created only when ColPali is enabled)."),
        ("Queue + cache", "Redis — Celery broker for bulk jobs, embed cache keyed by chunk fingerprint."),
        ("Observability", "Prometheus, Grafana, Jaeger — /metrics scrape, dashboards, OTLP traces for ingest and retrieval."),
    ])

    b.section("Request flow: a single question")
    b.numbered([
        "Browser issues POST /api/query with the doc_id, query, and provider; nginx proxies to rag-api on the internal network.",
        "FastAPI rate-limits the request per IP via slowapi, then validates the QueryBody schema.",
        "Optional PII redaction (Presidio + spaCy) runs on the query text. The PIIRedactor is constructed with an explicit en_core_web_sm NLP engine pinned to English — see Chapter 6 for why.",
        "RAGPipeline.query runs the full multimodal retrieval (text, tables, figures, optional page images) and returns ranked contexts.",
        "If retrieve_only is false, AnswerGenerator builds the cited prompt and calls OpenAI or Ollama. The system prompt is strict: answer ONLY from the numbered context passages, cite sources inline as [1], [2].",
        "The taxonomy guard inspects the answer; if TAXONOMY_BLOCK_FORBIDDEN=true and a forbidden classification appears, it replaces the answer with a structured refusal.",
        "The QueryResponse — answer + citations + retrieved contexts + latency — is returned. OTLP spans for retrieve and generate land in Jaeger; Prometheus counters for /query are incremented.",
    ])

    b.section("Request flow: bulk PDF ingest")
    b.numbered([
        "Browser issues POST /api/ingest/bulk/start with the folder name and total file count; the API creates a job record in Redis and returns a job_id.",
        "Each PDF is uploaded with POST /api/ingest/bulk/{job_id}/files; the API saves to data/raw/uploads/bulk/{job_id}/ on a shared volume.",
        "POST /api/ingest/bulk/{job_id}/run enqueues one Celery task per uploaded PDF.",
        "Workers (backend.scaling.workers) pull tasks, fingerprint each PDF, dedup against an in-process LSH cache plus the Qdrant content hash, and call RAGPipeline.ingest on new docs.",
        "Workers update Redis (bulk:job:{id}:status) and emit Prometheus metrics on INGEST_METRICS_PORT.",
        "Browser polls GET /api/ingest/bulk/{job_id} every second and renders the progress bar; on completion the document is selectable from the sidebar.",
    ])

    b.section("Why these boundaries")
    b.bullets([
        "API to pipeline: keeping the FastAPI layer thin means the same RAGPipeline runs in the eval harness, the Celery worker, and the API without any duplication. Tests do not have to spin up FastAPI.",
        "Worker to API: bulk ingest can saturate a CPU for minutes. Putting it on Celery + Redis means a single PDF upload from the chat UI cannot get queued behind a 500-PDF batch.",
        "Four Qdrant collections: text, tables, figures, and (optional) page images are embedded by different models and retrieved with different query hints. One collection per modality keeps the search index dense and the fusion logic in MultiModalRetriever explicit.",
        "OpenTelemetry: the same trace ID propagates from the FastAPI request through the embedder and back, which makes 'why was that query slow?' answerable from Jaeger without bisecting the code.",
    ])

    b.section("Configuration surface")
    b.para(
        "Every backend toggle lives in backend/core/config.py as a single "
        "pydantic-settings Settings class. There are no scattered os.getenv() "
        "calls. The full table is Chapter 12; the rule of thumb is that any "
        "knob worth flipping at runtime appears there, with an alias matching "
        "the SCREAMING_SNAKE_CASE environment variable."
    )
    b.note(
        "single source of truth",
        "If you find yourself reading a value from os.environ in a backend module, that is a bug — promote it to Settings instead. Both the eval harness and the API rely on get_settings() returning the same instance per process (it is wrapped in lru_cache).",
    )

    # =========================================================================
    # Chapter 3: Ingestion pipeline
    # =========================================================================
    b.chapter("The Ingestion Pipeline")

    b.para(
        "Ingestion is the four-step path from a PDF on disk to vectors in "
        "Qdrant: parse, enrich, embed, store. Each step is in its own module "
        "and is fully overridable. The whole thing lives behind "
        "RAGPipeline.ingest(path) and emits structured progress events when "
        "called via POST /ingest/stream — see Chapter 11 for the SSE protocol."
    )

    b.section("Parsing")
    b.para(
        "backend.ingestion.parsers registers one parser per modality. The "
        "ParserRegistry dispatches by file extension and chunk type. For PDFs "
        "the registry runs four parsers in sequence and merges their outputs."
    )
    b.kv_table([
        ("PDFTextParser", "PyMuPDF based. Extracts running text per page; inherits section headings to populate section_path on each chunk."),
        ("TableParser", "pdfplumber. Detects ruled tables via line-intersection; falls back to text extraction when no ruling is present."),
        ("FigureParser", "Caption-aware bounding boxes around image regions; labels (e.g. 'Figure 3: ...') are captured for labeled-asset retrieval."),
        ("PageImageParser", "Whole-page renders, only used when USE_COLPALI=true. Lets ColPali embed layout directly."),
    ])
    b.subsection("Document IDs are deterministic")
    b.para(
        "stable_doc_id() in backend/ingestion/parsers/base_parser.py hashes the "
        "path from the raw/ anchor down, after normalizing separators. The "
        "same PDF re-ingested from a Windows host (C:\\Users\\...\\raw\\file.pdf), "
        "a Linux container (/app/data/raw/file.pdf), or a relative path "
        "(data/raw/file.pdf) all upsert to the same Qdrant row instead of "
        "duplicating. This is tested cross-platform in CI."
    )
    b.subsection("OCR for image-only pages")
    b.para(
        "When USE_OCR=true (default), Tesseract via pytesseract runs against "
        "pages that produced no parseable text and no images either. The "
        "fallback path is explicit: PDFParseError is raised when a page is "
        "neither parseable nor renderable, with a hint that the document may "
        "be scanned-only without OCR. The user-visible error surface in the "
        "frontend reflects this — empty pages don't silently disappear."
    )

    b.section("Enrichment")
    b.para(
        "backend.retrieval.preprocessing runs at ingest time so the cost is "
        "paid once per document, not per query. Each step is a feature flag:"
    )
    b.kv_table([
        ("USE_RECURSIVE_CHUNKER", "Token-aware splitter (max 512, overlap 64). Off by default; recommended on for production."),
        ("USE_SEMANTIC_CHUNKER", "Alternative to recursive — splits on cosine-distance boundaries between consecutive sentences. Threshold tunable via SEMANTIC_CHUNK_THRESHOLD (default 0.75)."),
        ("USE_SECTION_PATHS", "Attach the heading chain (Executive Summary > Q4 Highlights) to each chunk."),
        ("USE_CONTEXT_ENRICHMENT", "Pre-compute the [context] previous sentence + chunk + next sentence block used to disambiguate retrieved fragments."),
        ("USE_PII_REDACTION_ON_INGEST", "Presidio + spaCy redact emails, phone numbers, credit cards, IBANs, IPs, SSNs, passports, and a few more, before the vector store ever sees them."),
    ])

    b.section("Embedding")
    b.para(
        "backend.ingestion.embeddings routes chunks to one of three embedders "
        "based on chunk type. The text and image branches are required; the "
        "ColPali branch is opt-in and useful for layout-heavy documents."
    )
    b.kv_table([
        ("TextEmbedder", "BAAI/bge-m3 by default (1024-d). Multilingual, strong on long-context retrieval. Runs on cuda when EMBEDDING_DEVICE=cuda."),
        ("ImageEmbedder", "laion/CLIP-ViT-B-32-laion2B-s34B-b79K. Embeds figures and table images into a shared text/image space so figure retrieval works with text queries."),
        ("ColPaliEmbedder", "vidore/colqwen2-v1.0 by default (vidore/colSmol-500M for CPU). Embeds whole rendered pages; used when USE_COLPALI=true."),
    ])
    b.para(
        "embed_chunks batches by modality and caches by chunk fingerprint in "
        "Redis (embedding_cache_ttl_seconds defaults to 7 days). A re-ingest "
        "of an unchanged PDF is essentially free; a re-ingest after a chunker "
        "change pays only for the new chunks."
    )
    b.note(
        "torch and transformers compatibility",
        "transformers 5.x refuses to load model weights under torch < 2.6 (CVE-2025-32434). The Docker image pins torch>=2.6 and defaults to the cu124 wheel for GPU builds; the cu121 index only ships torch 2.5.x. Mismatched stacks surface as 503 on /query with an actionable message instead of a generic Internal Server Error.",
    )

    b.section("Storage")
    b.para(
        "QdrantStore in backend/ingestion/stores/qdrant_store.py writes one "
        "row per chunk into the matching collection (text_chunks, "
        "table_chunks, figure_chunks, page_chunks). Each row carries enough "
        "metadata for the frontend's 'open the citation' action to deep-link "
        "into the PDF viewer:"
    )
    b.bullets([
        "doc_id — the deterministic stable_doc_id, used as the partition key for all retrieval.",
        "source_path — original PDF path (relative to data/raw/).",
        "page_number — 1-indexed page on which the chunk appears.",
        "chunk_type — text / table / figure / page_image.",
        "section_path — the heading chain when USE_SECTION_PATHS=true.",
        "bbox — bounding box for figures and tables, used by the frontend overlay.",
        "content — the text or, for images, a textual surrogate (caption + alt text).",
        "content_hash — SHA-256 of the raw chunk text, used for cross-job dedup at bulk-ingest time.",
    ])

    b.section("Progress events")
    b.para(
        "RAGPipeline.ingest accepts an optional on_progress callback that the "
        "POST /ingest/stream endpoint wires to a Server-Sent Events stream. "
        "Stage names are stable: parsing, enriching, redacting, embedding, "
        "indexing. The detail payload includes chunk_count, vector_count, and "
        "vectors_by_collection where applicable. The frontend uses these "
        "events to drive the upload spinner and a real per-stage label."
    )
    b.code(
        "event: progress\n"
        "data: {\"stage\":\"parsing\",\"message\":\"Reading PDF pages...\"}\n"
        "\n"
        "event: progress\n"
        "data: {\"stage\":\"embedding\",\"message\":\"Embedding 8733 chunks...\",\"detail\":{\"chunk_count\":8733}}\n"
        "\n"
        "event: done\n"
        "data: {\"doc_id\":\"5c77f0e3a96a4de4\",\"chunk_count\":8733, ... }"
    )

    # =========================================================================
    # Chapter 4: Retrieval
    # =========================================================================
    b.chapter("Retrieval Strategy")

    b.para(
        "Retrieval is the bulk of DocuMind's complexity. The goal: given a "
        "natural-language question, return the smallest set of chunks (text, "
        "tables, figures, optionally page images) that lets the LLM answer "
        "with citations. This chapter walks every stage that lives under "
        "backend/retrieval/."
    )

    b.section("The high-level flow")
    b.code(
        "question\n"
        "  |\n"
        "  +-- modality hint? (Figure 3, Table 1, page N)\n"
        "  v\n"
        "per-collection search (text, tables, figures, pages -- parallel)\n"
        "  |\n"
        "  v\n"
        "hybrid: BM25 + dense within text_chunks\n"
        "  |\n"
        "  v\n"
        "Reciprocal Rank Fusion across collections\n"
        "  |\n"
        "  v\n"
        "parent-chunk expansion\n"
        "  |\n"
        "  v\n"
        "(optional) cross-encoder or FlashRank rerank\n"
        "  |\n"
        "  v\n"
        "top-K -> AnswerGenerator"
    )

    b.section("Modality routing")
    b.para(
        "MultiModalRetriever uses cheap regex/keyword heuristics to detect "
        "modality hints in the question. The hint biases — it does not gate — "
        "so a question like 'what does Figure 3 show' still searches text in "
        "case the answer is in the figure's caption rather than the figure "
        "itself."
    )
    b.kv_table([
        ("'table', 'row', 'column', 'Table N'", "boost table_chunks"),
        ("'figure', 'chart', 'plot', 'Figure N'", "boost figure_chunks"),
        ("'on page N', 'appendix N'", "apply page_number Qdrant filter"),
        ("no hint", "all collections searched equally"),
    ])

    b.section("Hybrid retrieval (text only)")
    b.para(
        "When USE_HYBRID=true (off by default; recommended on for production), "
        "HybridRetriever combines dense and sparse search:"
    )
    b.bullets([
        "Dense: top-K nearest neighbours from Qdrant on the BGE-M3 embedding of the question.",
        "Sparse: BM25 over the same chunks, using rank-bm25 with a tokenizer that handles numeric tokens and hyphenated terms.",
    ])
    b.para("The two lists are merged with Reciprocal Rank Fusion:")
    b.code("score(c) = sum over retrievers r of  1 / (k + rank_r(c))      where k = 60")
    b.para(
        "RRF is rank-based rather than score-based, so we do not need to "
        "normalize BM25 and cosine scales — a long-standing source of "
        "fragility in hybrid search. Why both? BGE-M3 dense vectors handle "
        "synonyms ('revenue' is close to 'income') and paraphrasing; BM25 handles "
        "exact strings the embedder does not care about ('Q4 2024', "
        "'$191.7M'). The combination beats either alone on the golden set."
    )

    b.section("Multimodal fusion across collections")
    b.para(
        "After per-collection retrieval, RRF runs again — this time fusing "
        "the top results from text_chunks, table_chunks, figure_chunks, and "
        "(if enabled) page_chunks. Modality hints simply add a small constant "
        "boost to the relevant collection's rank. The output is a single "
        "ranked list of RetrievedContext objects."
    )

    b.section("Parent-chunk expansion")
    b.para(
        "When USE_PARENT_EXPAND=true (default), a hit on a small 'child' "
        "chunk pulls in its neighbouring siblings to form a richer context. "
        "This solves the classic chunking trade-off:"
    )
    b.bullets([
        "Small chunks (around 256 tokens) rank well because they are focused, but they truncate the surrounding evidence.",
        "Large chunks (around 1024 tokens) carry more context but rank worse because the signal-to-noise drops.",
    ])
    b.para(
        "DocuMind embeds the small chunks but, on a hit, expands to the parent "
        "passage. The expansion logic lives in backend/retrieval/parent_expand.py."
    )

    b.section("Labeled-asset retrieval")
    b.para(
        "Tables and figures often have explicit labels — Table 1, Figure 3. "
        "backend/retrieval/asset_refs.py detects these references in both the "
        "query and the chunk metadata, and adds them as a high-precedence "
        "path on top of the vector/BM25/RRF stack. This means 'What does "
        "Figure 3 show?' directly retrieves the chunk that was labeled "
        "'Figure 3' by the parser at ingest time — no embedding match required."
    )

    b.section("Optional rerankers")
    b.kv_table([
        ("Cross-encoder", "BAAI/bge-reranker-v2-m3, ~250 ms for 10 chunks on CPU. Best quality, ~10× slower than no reranker."),
        ("FlashRank", "ms-marco-MiniLM-L-12-v2, ~25 ms for 10 chunks. Solid quality, almost free latency. Set USE_FLASHRANK=true."),
    ])
    b.para(
        "Both rerankers shrink the retrieved-context list from default_top_k "
        "(5) down to reranker_top_n (3) before the LLM call, which also makes "
        "the LLM cheaper."
    )

    b.section("ColPali (page-image retrieval)")
    b.para(
        "When USE_COLPALI=true, DocuMind also embeds whole rendered pages "
        "with a vision-language model (default vidore/colqwen2-v1.0). This is "
        "useful for documents where the layout itself encodes information — "
        "forms, multi-column scientific papers, slide decks — where the text "
        "embedder loses information that ColPali keeps. Practical notes: "
        "ColPali needs a GPU to be tolerable (use vidore/colSmol-500M for "
        "CPU), and it is purely additive — the page_chunks collection "
        "participates in RRF fusion just like text, tables, and figures."
    )

    b.section("Chunk filters")
    b.para(
        "backend/retrieval/chunk_filters.py runs cheap post-retrieval filters "
        "before the LLM call:"
    )
    b.bullets([
        "is_substantive_content: drops chunks whose visible text is whitespace, single characters, or page numbers — common artefacts from OCR on scanned PDFs.",
        "Dedup by chunk_id: same chunk surfacing from both dense and sparse retrieval is collapsed.",
    ])
    b.para(
        "If every retrieved chunk fails is_substantive_content, the generator "
        "short-circuits to the 'no searchable text' fallback rather than "
        "asking the LLM to answer from nothing."
    )

    b.section("Why this stack")
    b.kv_table([
        ("Hybrid (BM25 + dense) + RRF", "Real questions cite specific numbers and identifiers. Dense alone misses them; RRF without rescaling is robust."),
        ("Separate collection per modality", "Different embedding models per modality means different vector dimensionalities. Qdrant needs separate collections."),
        ("Parent expansion", "Decouples what we index for ranking from what we feed the LLM."),
        ("Optional rerankers", "Quality / latency knob the operator owns. CI runs without; production can flip the toggle."),
        ("ColPali behind a flag", "Costs a GPU; only worth it for layout-heavy corpora."),
    ])

    # =========================================================================
    # Chapter 5: Answer generation
    # =========================================================================
    b.chapter("Answer Generation")

    b.section("The cited-context prompt")
    b.para(
        "AnswerGenerator builds a numbered context block where every entry "
        "names its page and chunk type. The LLM is given a strict system "
        "prompt: answer ONLY using the numbered context passages, cite "
        "sources inline as [1], [2]. If the context is insufficient, the "
        "model is instructed to say so rather than guess."
    )
    b.code(
        "[1] (page 2, text)\n"
        "Executive Summary. Acme Corp delivered strong financial performance in 2024.\n"
        "Total revenue reached $191.7M, a 24% year-over-year increase.\n"
        "\n"
        "[2] (page 3, table)\n"
        "Quarter | Revenue ($M) | YoY Growth | Net Margin\n"
        "Q1 2024 | 41.2 | +18% | 9.4%\n"
        "Q2 2024 | 46.7 | +21% | 10.8%\n"
        "Q3 2024 | 49.2 | +25% | 11.5%\n"
        "Q4 2024 | 54.6 | +32% | 12.7%"
    )

    b.section("Citation objects")
    b.para(
        "The response is wrapped in a QueryResponse with Citation objects "
        "that carry doc_id, source_path, page_number, chunk_id, and a trimmed "
        "excerpt. The frontend uses those to render clickable citation badges "
        "and open the source panel."
    )
    b.code(
        "{\n"
        "  \"answer\": \"Q4 2024 revenue was $54.6M [2].\",\n"
        "  \"citations\": [\n"
        "    {\n"
        "      \"doc_id\": \"ed7d53f9b08caa39\",\n"
        "      \"source_path\": \"data/raw/sample_report.pdf\",\n"
        "      \"page_number\": 3,\n"
        "      \"chunk_id\": \"table_3_0\",\n"
        "      \"excerpt\": \"Q4 2024 | 54.6 | +32% | 12.7%\"\n"
        "    }\n"
        "  ],\n"
        "  \"latency_ms\": 1842.3\n"
        "}"
    )

    b.section("LLM providers")
    b.kv_table([
        ("openai", "OPENAI_API_KEY required; OPENAI_MODEL defaults to gpt-4o. The Vision model (gpt-4o by default) is reused for figure-bearing answers."),
        ("ollama", "OLLAMA_BASE_URL points to a local Ollama instance. In Docker, set to http://host.docker.internal:11434. The default model is llama3.2; override via the request body."),
    ])
    b.para(
        "The provider is selected per request via the provider field on the "
        "query body. The frontend exposes it as a dropdown in the sidebar so "
        "you can switch between OpenAI and a local Ollama without restarting."
    )

    b.section("Fallback paths")
    b.bullets([
        "No retrieved context: the generator returns a friendly fallback ('This document may be image-only; re-upload to run OCR') instead of hallucinating from nothing.",
        "Only non-substantive context: same fallback fires when every retrieved chunk fails is_substantive_content.",
        "LLM unreachable: the generator catches the connection error and returns the retrieved contexts with answer='LLM provider unavailable; see citations below' so the user still gets sources.",
        "Taxonomy block: with TAXONOMY_BLOCK_FORBIDDEN=true, an answer that mentions a forbidden classification is replaced with a structured refusal. See Chapter 6 for the conformity check.",
    ])

    b.section("Streaming")
    b.para(
        "POST /query/stream is a Server-Sent Events endpoint that emits a "
        "single answer event when generation finishes. Token-by-token "
        "streaming is straightforward — wire the OpenAI streaming response "
        "to the SSE producer in answer_generator.py — but is not yet wired "
        "to the frontend. The same SSE machinery used for /ingest/stream is "
        "ready to consume it (see backend/api/routers/query.py and "
        "frontend/src/utils/sse.ts)."
    )

    # =========================================================================
    # Chapter 6: Guardrails
    # =========================================================================
    b.chapter("Guardrails")

    b.para(
        "Four guardrails sit at well-defined points in the request lifecycle. "
        "Each is independently togglable; none is a heavyweight middleware "
        "you have to opt out of."
    )

    b.section("PII redaction")
    b.para(
        "Presidio Analyzer + Anonymizer, backed by spaCy en_core_web_sm, run "
        "in two places:"
    )
    b.kv_table([
        ("USE_PII_REDACTION_ON_INGEST", "Redact chunk content before it is embedded and stored. Anything indexed has already been sanitized; downstream retrieval cannot accidentally surface raw PII."),
        ("USE_PII_REDACTION", "Redact /query input and /query output (answer + citation excerpts + retrieved chunk text) for defense in depth."),
    ])
    b.para(
        "The entity list is contact and financial identifiers only: "
        "EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, US_SSN, US_BANK_NUMBER, "
        "IBAN_CODE, US_PASSPORT, IP_ADDRESS, MEDICAL_LICENSE, CRYPTO. "
        "US_DRIVER_LICENSE and DATE_TIME are deliberately omitted — they "
        "produce too many false positives on job references like 'e02' and "
        "fiscal quarters like 'Q1 2024' in business documents."
    )
    b.note(
        "the en_core_web_sm pin",
        "Presidio defaults to en_core_web_lg, which is ~400 MB and is downloaded on first analyze() call. DocuMind explicitly constructs the AnalyzerEngine with a NlpEngineProvider pointed at en_core_web_sm (12 MB, bundled into the Docker image). The PII entity list is regex-based; the small model is sufficient. This also silences the noisy 'Recognizer not added to registry because language is not supported' warnings and avoids a futile CUDA probe.",
    )

    b.section("Taxonomy conformity")
    b.para(
        "backend/taxonomy/ runs an RDF taxonomy validator against generated "
        "answers. The taxonomy file (data/taxonomies/) declares preferred, "
        "allowed, and forbidden classifications; fuzzy entity linking maps "
        "answer phrases to taxonomy classes. The conformity check produces a "
        "structured ConformityMeta object on the response:"
    )
    b.code(
        "{\n"
        "  \"conformity\": {\n"
        "    \"score\": 0.93,\n"
        "    \"flagged\": false,\n"
        "    \"forbidden_terms\": []\n"
        "  }\n"
        "}"
    )
    b.bullets([
        "USE_TAXONOMY_VALIDATION=true (default): always evaluate; expose the score and any flags in the response metadata.",
        "TAXONOMY_BLOCK_FORBIDDEN=true: when a forbidden term is detected, the answer is replaced with a structured refusal. The frontend renders a ConformityBanner that explains which term was the problem.",
        "TAXONOMY_BLOCK_FORBIDDEN=false (default): warn and annotate only; the answer is still returned.",
    ])

    b.section("Rate limiting")
    b.para(
        "slowapi limits requests per IP. There are two ceilings, one for "
        "interactive endpoints and a much higher one for bulk uploads which "
        "may legitimately fire hundreds of requests in a minute:"
    )
    b.kv_table([
        ("API_RATE_LIMIT_PER_MINUTE (default 60)", "Applies to POST /query, POST /ingest, POST /ingest/stream, GET /admin/*."),
        ("API_RATE_LIMIT_BULK_PER_MINUTE (default 2000)", "Applies to the bulk upload endpoints and job-status polling."),
    ])
    b.para(
        "Limits are computed against X-Forwarded-For when nginx is in front "
        "of the API, so real client IPs are honoured. A 429 response is "
        "returned with a Retry-After header; the frontend surfaces this with "
        "an exponential backoff in the bulk-upload code path."
    )

    b.section("CORS")
    b.para(
        "CORS_ALLOW_ORIGINS is a comma-separated list. The default value '*' "
        "is appropriate only for local demos. In production, set explicit "
        "origins:"
    )
    b.code(
        "CORS_ALLOW_ORIGINS=https://docu.example.com,https://www.docu.example.com"
    )
    b.para(
        "When the value is anything other than '*', the CORSMiddleware also "
        "enables allow_credentials=True so cookies and Authorization headers "
        "are honoured. With wildcard origins, credentials are off per the "
        "CORS spec."
    )

    # =========================================================================
    # Chapter 7: Evaluation
    # =========================================================================
    b.chapter("Evaluation")

    b.para(
        "A RAG system that is not evaluated is mostly guesswork. DocuMind "
        "ships a small, hand-curated golden set and runs the same metrics in "
        "CI, the eval workflow, and any local checkout — so a regression is "
        "caught before it gets merged."
    )

    b.section("The golden set")
    b.para(
        "tests/eval/golden_set.jsonl is a JSONL of cases over "
        "data/raw/sample_report.pdf — a synthetic but realistic annual "
        "report with text, a table, and a figure across three pages. The "
        "sample PDF is byte-reproducible via SOURCE_DATE_EPOCH."
    )
    b.code(
        "{\n"
        "  \"id\": \"fig3-q4\",\n"
        "  \"query\": \"What was Q4 2024 revenue according to Figure 3?\",\n"
        "  \"doc_id\": \"ed7d53f9b08caa39\",\n"
        "  \"source_pdf\": \"data/raw/sample_report.pdf\",\n"
        "  \"relevant_pages\": [2],\n"
        "  \"reference_answer\": \"Q4 2024 revenue was $54.6M.\",\n"
        "  \"key_phrases\": [\"54.6\", \"Q4 2024\"]\n"
        "}"
    )
    b.para("The cases deliberately span all three retrieval modalities:")
    b.kv_table([
        ("Total revenue, NRR, FCF", "text (page 1)"),
        ("Quarterly revenue trend, DataPulse", "figure caption + body (page 2)"),
        ("Q3 margin, Q1 2025 row, board target", "table (page 3)"),
    ])
    b.para(
        "If a code change improves text retrieval but breaks figure retrieval, "
        "the metrics shift visibly — that is the whole point of the modality "
        "coverage."
    )

    b.section("Metrics")
    b.kv_table([
        ("Recall@5", "Of the pages that should appear, how many did we return in the top 5? Averaged across the golden set."),
        ("Hit@5", "Did at least one relevant page appear in the top 5? Binary per case, averaged."),
        ("MRR", "Reciprocal rank of the first relevant page. Penalises burying the right answer behind irrelevant ones."),
        ("Keyword coverage", "Fraction of key_phrases that appear in the generated answer. Cheap proxy for faithfulness without an LLM judge."),
        ("p95 retrieval latency (ms)", "After dropping the first cold query for warmup, p95 of the retrieve-only wall clock. Catches an O(N²) regression before it ships."),
        ("Faithfulness (Ragas)", "Optional, gated by pip install -e .[eval] and RUN_RAGAS_EVAL=1. LLM judge scores whether the answer is grounded in the retrieved contexts."),
    ])

    b.section("CI gates")
    b.para(
        "The thresholds live next to the application config so the same "
        "numbers are honoured in CI, the eval workflow, the API, and local "
        "runs:"
    )
    b.code(
        "# backend/core/config.py\n"
        "eval_recall_at_5_threshold: float = 0.70\n"
        "eval_hit_at_5_threshold:    float = 0.80\n"
        "eval_mrr_threshold:          float = 0.50\n"
        "eval_keyword_coverage_threshold: float = 0.66\n"
        "eval_faithfulness_threshold: float = 0.85\n"
        "eval_retrieval_latency_p95_ms: float = 60_000.0"
    )
    b.para(
        "The eval test fails (red CI) if any of these aren't met. Every "
        "threshold is also exposed as a EVAL_* env var so a flaky CPU runner "
        "can be tuned without rewriting the test."
    )

    b.section("Workflows")
    b.kv_table([
        ("eval.yml → retrieval-eval", "Weekly cron, every push touching backend/retrieval/, backend/ingestion/, tests/eval/, or backend/core/pipeline.py, and on demand. Spins up Qdrant as a service container, regenerates the sample PDF reproducibly, ingests it, runs the retrieval eval, emits a Markdown benchmark summary to the GitHub Actions run page, and uploads benchmarks.md as an artifact."),
        ("eval.yml → answer-eval", "Same triggers, gated on OPENAI_API_KEY repo secret via a check-secrets job whose has_openai_key output the answer-eval job consumes via needs:. This is the documented workaround for GitHub Actions not reliably evaluating secrets.* inside if:."),
    ])

    b.section("Reproducing the benchmarks locally")
    b.code(
        "( cd docker && docker compose up -d qdrant )\n"
        "python scripts/generate_sample_report.py      # one-off, also tracked in git\n"
        "pytest tests/eval/test_retrieval.py tests/eval/test_metrics.py -m eval -v"
    )
    b.para("Generate the same Markdown table the workflow uploads:")
    b.code(
        "python scripts/run_eval_report.py             # prints to stdout\n"
        "python scripts/run_eval_report.py -o bench.md # writes to file"
    )

    # =========================================================================
    # Chapter 8: Observability
    # =========================================================================
    b.chapter("Observability")

    b.para(
        "Three signals are exported by default: traces, metrics, and "
        "structured logs. Each goes to a sidecar service in the Compose stack "
        "so you do not need a SaaS account to debug a slow query."
    )

    b.section("Traces — OpenTelemetry to Jaeger")
    b.para(
        "FastAPI is instrumented via opentelemetry-instrumentation-fastapi. "
        "Every request gets a span tree that includes:"
    )
    b.bullets([
        "The HTTP server span (FastAPI).",
        "Retrieval spans per Qdrant collection.",
        "An embedding span per modality.",
        "A generation span around the LLM call.",
        "An anonymizer span around PII redaction.",
    ])
    b.para(
        "Set OTLP_ENDPOINT to your collector. In the Compose stack this is "
        "http://jaeger:4317. The Jaeger UI is on http://localhost:16686."
    )

    b.section("Metrics — Prometheus + Grafana")
    b.para(
        "FastAPI exposes /metrics. The Counters and Histograms in "
        "backend/api/monitoring/metrics.py are:"
    )
    b.bullets([
        "QUERY_REQUESTS{provider,retrieve_only} — counter for /query.",
        "QUERY_LATENCY — histogram of /query end-to-end latency.",
        "INGEST_REQUESTS — counter for /ingest and /ingest/stream.",
        "PII_REDACTIONS — counter for every redaction that fired on input or output.",
    ])
    b.para(
        "The Celery worker exposes a separate Prometheus port "
        "(INGEST_METRICS_PORT, default 9100) with per-job ingest counters. "
        "Both endpoints are scraped by the Prometheus container; the Grafana "
        "container ships with a dashboard preconfigured in "
        "docker/grafana/dashboards/."
    )

    b.section("Structured logs")
    b.para(
        "structlog renders JSON to stdout. LOG_LEVEL controls verbosity. The "
        "common keys are trace_id (from OpenTelemetry), doc_id, chunk_count, "
        "and provider. With Docker, docker compose logs -f rag-api is enough "
        "to follow a request; in production, ship to your log aggregator and "
        "key on trace_id to join across services."
    )

    b.section("Health and readiness")
    b.kv_table([
        ("GET /health", "Always 200 if the process is up. Useful for a TCP-level health check."),
        ("GET /ready", "Probes Qdrant and Redis, and, when API_WARMUP_MODELS=true, reports whether the embedding models loaded successfully. Returns 503 if any check fails."),
        ("GET /metrics", "Prometheus exposition. Not protected — bind only on the internal network in production."),
    ])

    # =========================================================================
    # Chapter 9: Scaling
    # =========================================================================
    b.chapter("Scaling Out")

    b.section("Why a worker tier")
    b.para(
        "Single-PDF /ingest runs synchronously in the API process because it "
        "is the simplest UX for the chat tab. For folders of hundreds of "
        "PDFs that is the wrong shape: a multi-hour batch should not keep a "
        "browser tab open and should not block other users from querying. "
        "DocuMind moves bulk ingest onto Celery with Redis as the broker."
    )

    b.section("The bulk-ingest protocol")
    b.numbered([
        "Browser: POST /ingest/bulk/start with the folder name and total file count → API creates a Redis job record and returns job_id.",
        "Browser: POST /ingest/bulk/{job_id}/files repeatedly, one per PDF; API saves each to data/raw/uploads/bulk/{job_id}/.",
        "Browser: POST /ingest/bulk/{job_id}/run → API enqueues one Celery task per PDF onto Redis.",
        "Workers: pull tasks; fingerprint each PDF; dedup against an in-process LSH cache plus the Qdrant content hash; call RAGPipeline.ingest on new docs.",
        "Browser: GET /ingest/bulk/{job_id} every second; renders the progress bar.",
        "Optional: POST /ingest/bulk/{job_id}/resume — requeue any files that errored or never started, without re-uploading.",
    ])

    b.section("Deduplication")
    b.para(
        "Bulk ingest of a corpus that already lives in the index is "
        "expensive. Two layers of dedup prevent the obvious waste:"
    )
    b.bullets([
        "Per-task: the worker computes an LSH minhash over the PDF text. If a fingerprint within DEDUP_SIMILARITY_THRESHOLD (default 0.85) has already been seen in the same job, the second occurrence is skipped.",
        "Per-corpus: each chunk's content_hash is checked against Qdrant before upsert. Re-ingesting an unchanged PDF is a near-no-op: parse + embed are cached in Redis (embedding_cache_ttl_seconds = 7 days), and Qdrant rejects already-present rows.",
    ])

    b.section("Caching")
    b.para(
        "The embedding cache is keyed by (model_name, chunk_fingerprint). On "
        "a cache hit, the embedder returns the cached vector without touching "
        "the model. This is what makes a re-ingest after a chunker change "
        "fast: only the chunks that actually changed are re-embedded."
    )

    b.section("Sizing notes")
    b.kv_table([
        ("CPU only", "BGE-M3 on a modern x86 server: ~50–80 chunks/sec. A 200-page PDF with text + tables produces ~600–1000 chunks; expect ~10–15 s of embedding time per doc plus parse + upsert."),
        ("GPU (RTX 3070 Ti, 8 GB)", "BGE-M3 saturates the GPU at batch_size 32; ~5–8× faster than CPU. VRAM is shared between BGE-M3 (~2 GB) and CLIP (~1 GB); ColPali adds 3–4 GB and tips you over 8 GB on a -B model."),
        ("Concurrent workers", "max_workers (default 4) bounds Celery prefetch. For CPU embedding, set CELERYD_CONCURRENCY to the number of physical cores."),
    ])

    # =========================================================================
    # Chapter 10: Deployment
    # =========================================================================
    b.chapter("Deployment")

    b.section("Local Docker Compose")
    b.para(
        "The default stack lives in docker/docker-compose.yml. It defines the "
        "rag-api, ingest-worker, documind-web (nginx), qdrant, redis, "
        "prometheus, grafana, and jaeger services, plus their networks and "
        "volumes."
    )
    b.code(
        "cp .env.example .env\n"
        "# put your OPENAI_API_KEY (or set OLLAMA_BASE_URL) in .env\n"
        "cd docker\n"
        "docker compose --profile production up -d --build"
    )
    b.para(
        "First start downloads embedding models (~15–30 minutes on a slow "
        "network, faster on subsequent rebuilds because the Hugging Face "
        "cache is a named volume). With API_WARMUP_MODELS=true (default), the "
        "API will not pass /ready until the models are loaded."
    )

    b.section("GPU build")
    b.para(
        "An overlay file at docker/docker-compose.gpu.yml flips the build to "
        "the cu124 PyTorch wheel and reserves NVIDIA GPUs for rag-api and "
        "ingest-worker. The host must have the NVIDIA Container Toolkit "
        "(Linux) or Docker Desktop with WSL2 GPU support (Windows)."
    )
    b.code(
        "cd docker\n"
        "docker compose -f docker-compose.yml -f docker-compose.gpu.yml \\\n"
        "  --profile production up -d --build"
    )
    b.note(
        "torch version pin",
        "transformers 5.x refuses to load model weights under torch < 2.6 due to CVE-2025-32434. The Dockerfile pins torch>=2.6.0; the GPU overlay defaults to the cu124 wheel index because the cu121 index caps at torch 2.5.1. If your driver is too old for CUDA 12.4, set TORCH_INDEX_URL in your shell before building.",
    )

    b.section("Fly.io")
    b.para(
        "deploy/fly.toml ships a working Fly configuration. The defaults pick "
        "a 2-CPU/4-GB VM, mount a volume for the Qdrant data directory, and "
        "set API_WARMUP_MODELS=true. The deploy/README.md walks through "
        "secret setup and the first deploy."
    )

    b.section("nginx in front")
    b.para(
        "frontend/nginx.conf proxies /api/* to rag-api on the internal "
        "network and serves the static frontend bundle. Timeouts and "
        "buffering settings are tuned for two real workloads — long PDF "
        "uploads and Server-Sent Events:"
    )
    b.kv_table([
        ("proxy_send_timeout / proxy_read_timeout", "1200 s — long PDFs on CPU can spend many minutes in parse + OCR + embed before the upstream produces a response."),
        ("client_body_timeout / send_timeout", "1200 s — same reason on the client side."),
        ("proxy_request_buffering", "off — stream uploads straight to rag-api instead of buffering the entire multipart body in nginx."),
        ("proxy_buffering", "off — SSE (/ingest/stream, /query/stream) must flush each event immediately."),
        ("client_max_body_size", "100 m — caps a single upload at 100 MB."),
    ])

    b.section("CI / CD")
    b.kv_table([
        (".github/workflows/ci.yml", "Lints (ruff), runs pytest with Qdrant in services, type-checks the frontend, runs npm ci + npm run build. Triggers on push and pull_request for main and master."),
        (".github/workflows/eval.yml", "Weekly cron and path-triggered retrieval-eval. Publishes a benchmarks.md artifact and a GitHub Step Summary. The answer-eval job runs only when OPENAI_API_KEY is set, via the check-secrets guard."),
        (".github/workflows/wiki.yml", "Auto-syncs docs/wiki/ → the GitHub Wiki on every push to master that touches docs/wiki/**."),
    ])

    # =========================================================================
    # Chapter 11: API reference
    # =========================================================================
    b.chapter("API Reference")

    b.section("Health and metrics")
    b.kv_table([
        ("GET /health", "Liveness probe. Always 200 if the process is up. {\"status\": \"ok\"}."),
        ("GET /ready", "Readiness probe. Returns 200 only if Qdrant and Redis are reachable and (when warmup is enabled) the embedding models are loaded."),
        ("GET /metrics", "Prometheus exposition. Bind on the internal network only."),
    ])

    b.section("Query")
    b.subsection("POST /query")
    b.para("Single-shot query, JSON response.")
    b.code(
        "{\n"
        "  \"query\": \"What was Q4 2024 revenue?\",\n"
        "  \"top_k\": 5,\n"
        "  \"doc_id\": \"ed7d53f9b08caa39\",\n"
        "  \"provider\": \"openai\",\n"
        "  \"retrieve_only\": false,\n"
        "  \"block_forbidden\": null\n"
        "}"
    )
    b.subsection("POST /query/stream")
    b.para(
        "Same body as /query, but the response is a Server-Sent Events "
        "stream. Events: status (\"retrieving\"), answer (the full "
        "QueryResponse payload), done."
    )

    b.section("Ingest")
    b.kv_table([
        ("POST /ingest", "Upload a single PDF; runs the full pipeline synchronously and returns the IngestResponse."),
        ("POST /ingest/stream", "Same as /ingest but emits an SSE progress stream with stages: uploading, parsing, enriching, redacting, embedding, indexing. Terminal events: done (with the IngestResponse) or error."),
        ("POST /ingest/directory", "Server-side directory ingest. The body specifies a path under data/raw/; the API walks recursively (unless recursive=false) and runs the pipeline per PDF."),
    ])

    b.subsection("Bulk ingest")
    b.kv_table([
        ("POST /ingest/bulk/start", "{folder_name, total_files} → {job_id, total_files}. Creates an empty bulk job in Redis."),
        ("POST /ingest/bulk/{job_id}/files", "Upload one PDF (multipart). Returns {job_id, uploaded, total, filename}."),
        ("POST /ingest/bulk/{job_id}/run", "Enqueue Celery tasks for all uploaded files in the job. Returns {job_id, queued, status}."),
        ("POST /ingest/bulk/{job_id}/resume", "Re-enqueue files that errored or were never started; useful when a worker crashed mid-job."),
        ("GET /ingest/bulk/{job_id}", "Job status: total, uploaded, processed, ingested, skipped, failed, current_file, message."),
    ])

    b.section("Admin")
    b.kv_table([
        ("GET /admin/documents", "List ingested documents (doc_id, name, source_path, chunk_count)."),
        ("GET /admin/documents/{doc_id}/suggestions", "Cached question suggestions for a document, used by the chat panel."),
        ("GET /admin/documents/{doc_id}/file", "Stream the original PDF. Used by the frontend preview pane."),
        ("GET /admin/directories", "Browse server-side directories under data/raw/."),
        ("GET /admin/collections", "Qdrant collection stats: name, points_count, vector_size."),
        ("DELETE /admin/doc/{doc_id}", "Remove all chunks for a document across every collection."),
    ])

    # =========================================================================
    # Chapter 12: Configuration reference
    # =========================================================================
    b.chapter("Configuration Reference")

    b.para(
        "Every backend setting comes from backend/core/config.py — a single "
        "pydantic-settings Settings class. Override anything via .env "
        "(gitignored) or real environment variables; aliases below are what "
        "you put in the env."
    )

    b.section("LLM provider")
    b.kv_table([
        ("OPENAI_API_KEY", "Required for OpenAI mode. Empty by default."),
        ("OPENAI_MODEL", "Default gpt-4o. OpenAI chat model."),
        ("OLLAMA_BASE_URL", "Default http://localhost:11434. In Docker: http://host.docker.internal:11434."),
        ("HF_TOKEN", "Optional Hugging Face token for faster / gated model downloads."),
    ])

    b.section("Embeddings and retrieval models")
    b.kv_table([
        ("TEXT_EMBEDDING_MODEL", "Default BAAI/bge-m3. Multilingual text encoder."),
        ("COLPALI_MODEL", "Default vidore/colqwen2-v1.0. Use vidore/colSmol-500M on CPU."),
        ("USE_COLPALI", "Default false. Enable page-image retrieval; GPU recommended."),
        ("EMBEDDING_DEVICE", "Default cpu. Set to cuda when a GPU is present."),
    ])

    b.section("Retrieval toggles")
    b.kv_table([
        ("USE_HYBRID", "Default false. BM25 + dense fusion on text_chunks. Recommended true for production."),
        ("USE_RECURSIVE_CHUNKER", "Default false. Token-aware splitter."),
        ("USE_SEMANTIC_CHUNKER", "Default false. Alternative to recursive — splits on cosine boundaries."),
        ("SEMANTIC_CHUNK_THRESHOLD", "Default 0.75. Cosine threshold for the semantic chunker."),
        ("USE_SECTION_PATHS", "Default true. Carry the heading chain on every chunk."),
        ("USE_CONTEXT_ENRICHMENT", "Default true. Pre-compute neighbouring-sentence context windows at ingest."),
        ("USE_PARENT_EXPAND", "Default true. On a child-chunk hit, expand to the parent passage."),
        ("USE_FLASHRANK", "Default false. Lightweight cross-encoder rerank (~25 ms per 10 chunks)."),
    ])

    b.section("Vector DB and queue")
    b.kv_table([
        ("QDRANT_URL", "Default http://localhost:6333."),
        ("QDRANT_API_KEY", "Empty by default. Only needed for Qdrant Cloud."),
        ("REDIS_URL", "Default redis://localhost:6379."),
        ("CELERY_BROKER_URL", "Falls back to REDIS_URL. Override only if broker ≠ cache."),
        ("INGEST_METRICS_PORT", "Default 9100. Worker Prometheus port."),
        ("DEDUP_SIMILARITY_THRESHOLD", "Default 0.85. LSH similarity above which two PDFs are treated as duplicates at bulk-ingest time."),
    ])

    b.section("OCR and parsing")
    b.kv_table([
        ("USE_OCR", "Default true. Tesseract OCR for image-only PDF pages at ingest."),
        ("OCR_LANG", "Default eng. Tesseract language code."),
    ])

    b.section("API, guardrails, observability")
    b.kv_table([
        ("API_RATE_LIMIT_PER_MINUTE", "Default 60. Per-IP cap for /query and single-file /ingest."),
        ("API_RATE_LIMIT_BULK_PER_MINUTE", "Default 2000. Per-IP cap for bulk uploads and job-status polling."),
        ("CORS_ALLOW_ORIGINS", "Default *. Comma-separated origins; * disables credentials."),
        ("USE_PII_REDACTION", "Default true. Presidio + spaCy redaction on /query text."),
        ("USE_PII_REDACTION_ON_INGEST", "Default true. Same redaction at ingest."),
        ("USE_TAXONOMY_VALIDATION", "Default true. Run the RDF taxonomy guard on generated answers."),
        ("TAXONOMY_BLOCK_FORBIDDEN", "Default false. True hard-blocks forbidden mentions; false only warns."),
        ("API_WARMUP_MODELS", "Default true. Eager-load text / image / reranker models on boot."),
        ("OTLP_ENDPOINT", "Default http://localhost:4317. OpenTelemetry collector."),
        ("LOG_LEVEL", "Default INFO."),
    ])

    b.section("Evaluation thresholds")
    b.kv_table([
        ("EVAL_TOP_K", "Default 10. top_k used during the eval; metrics still cut at K=5."),
        ("EVAL_RECALL_AT_5_THRESHOLD", "Default 0.70."),
        ("EVAL_HIT_AT_5_THRESHOLD", "Default 0.80."),
        ("EVAL_MRR_THRESHOLD", "Default 0.50."),
        ("EVAL_KEYWORD_COVERAGE_THRESHOLD", "Default 0.66."),
        ("EVAL_RETRIEVAL_LATENCY_P95_MS", "Default 60000. Retrieve-only p95 ceiling after warmup."),
        ("RUN_RAGAS_EVAL", "Unset by default. Set to 1 after pip install -e .[eval] for LLM-judge faithfulness."),
    ])

    b.section("Reproducible builds")
    b.kv_table([
        ("SOURCE_DATE_EPOCH", "Default 1704067200 (2024-01-01 UTC). Pins every wall-clock leak in generated artefacts (sample PDF, this book, eval reports) so re-runs produce byte-identical outputs."),
    ])

    # =========================================================================
    # Appendix A: repo layout
    # =========================================================================
    b.appendix("Appendix A — Repository Layout")

    b.para("A bird's-eye view of every top-level directory in the repository.")
    b.code(
        "RAG/\n"
        "|-- backend/\n"
        "|   |-- api/                 # FastAPI routers, schemas, monitoring, guardrails\n"
        "|   |   |-- routers/         # health, query, ingest, bulk_ingest, admin\n"
        "|   |   |-- monitoring/      # metrics.py, tracing.py\n"
        "|   |   |-- guardrails/      # pii.py (Presidio + spaCy)\n"
        "|   |   |-- main.py          # FastAPI app + lifespan + CORS + rate limiting\n"
        "|   |   \\-- rate_limit.py\n"
        "|   |-- core/                # pipeline + config + shared models\n"
        "|   |   |-- pipeline.py      # RAGPipeline -- the single entry point\n"
        "|   |   |-- config.py        # pydantic-settings Settings\n"
        "|   |   \\-- models.py        # DocumentChunk, RetrievedContext, QueryResponse, ...\n"
        "|   |-- ingestion/\n"
        "|   |   |-- parsers/         # PDFTextParser, TableParser, FigureParser, PageImageParser\n"
        "|   |   |-- embeddings/      # TextEmbedder, ImageEmbedder, ColPaliEmbedder\n"
        "|   |   \\-- stores/          # qdrant_store.py\n"
        "|   |-- retrieval/\n"
        "|   |   |-- multimodal_retriever.py\n"
        "|   |   |-- hybrid_retriever.py\n"
        "|   |   |-- parent_expand.py\n"
        "|   |   |-- asset_refs.py\n"
        "|   |   |-- cross_encoder_reranker.py\n"
        "|   |   |-- flashrank_reranker.py\n"
        "|   |   |-- chunking/        # recursive + semantic chunkers\n"
        "|   |   |-- preprocessing.py # ingest-time enrichment dispatcher\n"
        "|   |   \\-- chunk_filters.py\n"
        "|   |-- generation/\n"
        "|   |   \\-- answer_generator.py\n"
        "|   |-- scaling/\n"
        "|   |   |-- workers.py       # Celery tasks (ingest_single_pdf_task, ...)\n"
        "|   |   |-- pipeline/        # ingest modes, scalable_ingest\n"
        "|   |   \\-- embedding/       # cached_embed.py\n"
        "|   \\-- taxonomy/            # RDF taxonomy validation, conformity\n"
        "|-- frontend/\n"
        "|   |-- src/\n"
        "|   |   |-- api/client.ts    # typed RagApiClient\n"
        "|   |   |-- components/      # PdfUploader, ChatPanel, CitationsPanel, ...\n"
        "|   |   |-- utils/           # sse.ts, renderLatex.ts, apiErrors.ts\n"
        "|   |   \\-- App.tsx\n"
        "|   \\-- nginx.conf\n"
        "|-- docker/\n"
        "|   |-- Dockerfile           # rag-api + ingest-worker image\n"
        "|   |-- docker-compose.yml   # base stack\n"
        "|   |-- docker-compose.gpu.yml  # GPU overlay (cu124)\n"
        "|   \\-- grafana/dashboards/  # preconfigured Grafana dashboard\n"
        "|-- docs/\n"
        "|   |-- wiki/                # version-controlled wiki source\n"
        "|   \\-- documind-book.pdf    # this book\n"
        "|-- tests/\n"
        "|   |-- eval/                # golden set + metrics + retrieval eval\n"
        "|   |-- api/                 # router-level tests\n"
        "|   |-- ingestion/, retrieval/, scaling/, taxonomy/\n"
        "|   \\-- test_pipeline.py     # RAGPipeline unit tests\n"
        "|-- scripts/\n"
        "|   |-- generate_sample_report.py     # byte-reproducible sample PDF\n"
        "|   |-- run_eval_report.py            # Markdown benchmark publisher\n"
        "|   |-- generate_bulk_pdfs.py         # corpus generator for load tests\n"
        "|   \\-- generate_book.py              # this script\n"
        "|-- deploy/\n"
        "|   \\-- fly.toml             # working Fly.io deployment\n"
        "|-- .github/workflows/       # ci.yml, eval.yml, wiki.yml\n"
        "|-- data/\n"
        "|   |-- raw/                 # input PDFs (sample_report.pdf is tracked)\n"
        "|   |-- processed/           # rendered pages and figures\n"
        "|   \\-- taxonomies/          # RDF/OWL taxonomy files\n"
        "|-- README.md\n"
        "|-- pyproject.toml\n"
        "\\-- .env.example"
    )

    # =========================================================================
    # Appendix B: troubleshooting
    # =========================================================================
    b.appendix("Appendix B — Troubleshooting")

    b.section("/query returns 503 with a torch upgrade message")
    b.para(
        "The embedding stack failed to load because torch is below 2.6 while "
        "transformers is 5.x. Rebuild the API container:"
    )
    b.code(
        "cd docker\n"
        "docker compose -f docker-compose.yml -f docker-compose.gpu.yml \\\n"
        "  --profile production build rag-api ingest-worker\n"
        "docker compose -f docker-compose.yml -f docker-compose.gpu.yml \\\n"
        "  --profile production up -d rag-api ingest-worker"
    )

    b.section("/query returns 'Internal Server Error'")
    b.para(
        "Check docker logs rag_api for a stack trace. The two common causes:"
    )
    b.bullets([
        "torch/transformers mismatch — see the previous section.",
        "Qdrant or Redis is unreachable — GET /ready will tell you which check is failing.",
    ])

    b.section("PDFParseError on a specific page")
    b.para(
        "The page produced no parseable text and no images. Causes: a "
        "scanned-only PDF without OCR (set USE_OCR=true and rebuild), or an "
        "intentionally blank page. The pipeline logs the page number and the "
        "doc_id; you can either re-OCR or accept the gap."
    )

    b.section("Long PDF upload returns 504 with raw HTML in the UI")
    b.para(
        "Pre-0.1.0 builds did not parse nginx HTML error pages and dumped the "
        "raw body into the UI. Update to the current frontend (parseApiErrorBody "
        "in frontend/src/utils/apiErrors.ts) and rebuild the documind-web "
        "container. The frontend now shows a single sentence and points the "
        "user at the async bulk-upload path or a GPU build."
    )

    b.section("Bulk ingest hangs on a single file")
    b.para(
        "Look at the worker log for the doc_id in question. Common culprits: "
        "an encrypted PDF (presented to the user as a parse error), a "
        "scanned-only PDF without OCR, or a single >100 MB page that pushes "
        "embedding past available VRAM. The bulk endpoint exposes resume "
        "semantics; you can skip the offending file and continue."
    )

    b.section("Sample PDF differs across machines")
    b.para(
        "SOURCE_DATE_EPOCH is the only knob that should change the output. If "
        "the sample PDF generated by scripts/generate_sample_report.py "
        "differs between machines despite the env var, check matplotlib + "
        "PyMuPDF versions; the pinned set in pyproject.toml is the only "
        "validated combination."
    )

    # =========================================================================
    # Appendix C: glossary
    # =========================================================================
    b.appendix("Appendix C — Glossary")

    b.kv_table([
        ("BGE-M3", "BAAI's multilingual text embedding model. Default text encoder. 1024-dim, supports long context."),
        ("CLIP", "Contrastive image-text encoder. Used to embed figure and table images into a shared text/image space."),
        ("ColPali", "Visual document encoder (vidore/colqwen2 or vidore/colSmol). Embeds whole rendered PDF pages; opt-in via USE_COLPALI=true."),
        ("Chunk", "An atomic unit of retrievable content: a text passage, a table, a figure, or a page image."),
        ("Citation", "A pointer from an answer to a specific chunk (doc_id, page_number, chunk_id) so the user can verify the claim."),
        ("Cross-encoder", "A model that scores a (query, document) pair jointly. Used as an optional reranker. More accurate than bi-encoders, much slower."),
        ("Dense retrieval", "Vector-similarity search over learned embeddings. Strong on semantics and paraphrase."),
        ("Eval gate", "A CI threshold above which a metric must remain. A regression below the gate fails CI."),
        ("FlashRank", "A lightweight cross-encoder reranker (~25 ms per 10 chunks). Good quality-per-latency ratio."),
        ("Golden set", "The hand-curated JSONL of evaluation cases. Each case has a query, the relevant pages, and key phrases to find in the answer."),
        ("Hit@K", "Binary metric: did at least one relevant page appear in the top K? Averaged across cases."),
        ("Hybrid retrieval", "Combination of dense and sparse (BM25) retrieval, fused with RRF."),
        ("LSH", "Locality-sensitive hashing. Used in bulk-ingest dedup to detect near-duplicate PDFs cheaply."),
        ("MRR", "Mean Reciprocal Rank. 1 / rank of the first relevant page, averaged across cases."),
        ("OCR", "Optical character recognition (Tesseract). Used at ingest for image-only PDF pages."),
        ("OTLP", "OpenTelemetry Protocol. The wire format used to ship traces from the API to Jaeger."),
        ("Parent expansion", "On a small-chunk hit, expand to the neighbouring sibling passages to give the LLM more context without losing retrieval precision."),
        ("Presidio", "Microsoft's PII analyzer and anonymizer. Wraps spaCy and a set of regex / pattern recognizers."),
        ("Qdrant", "Open-source vector database. DocuMind uses four collections — text_chunks, table_chunks, figure_chunks, page_chunks."),
        ("RAG", "Retrieval-Augmented Generation. The pattern this whole repository implements."),
        ("RRF", "Reciprocal Rank Fusion. A rank-based score combiner: 1 / (k + rank), summed across retrievers. k=60 by default. Robust because it ignores raw score scales."),
        ("SSE", "Server-Sent Events. The transport DocuMind uses for /ingest/stream progress and (in the future) /query/stream token streaming."),
        ("Stable doc ID", "The deterministic 16-character SHA-256 prefix of the path-from-raw of a PDF. The primary key for everything related to a document."),
        ("Section path", "The heading chain ('Executive Summary > Q4 Highlights') attached to each chunk by USE_SECTION_PATHS=true. Improves both retrieval and the LLM's situational awareness."),
        ("Taxonomy guard", "The RDF-based conformity check that scores generated answers against allowed and forbidden classifications."),
    ])

    # Now fill in the TOC pages
    b.render_toc()
    return b


def main() -> None:
    builder = build_book()
    builder.save(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH} — {len(builder.doc)} pages")


if __name__ == "__main__":
    main()
