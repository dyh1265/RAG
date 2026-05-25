"""Tests for PDF text block merging (algorithm pseudocode lines)."""

from __future__ import annotations

from backend.ingestion.parsers.pdf_text_parser import _merge_page_blocks


def test_merge_combines_short_numbered_algorithm_lines():
    blocks = [
        (10.0, 100.0, 400.0, 115.0, "Algorithm 2: Reduce vote column to a single match."),
        (10.0, 120.0, 300.0, 132.0, "1: int32 mask = 0xFFFFFFFF"),
        (10.0, 135.0, 350.0, 147.0, "2: if thread_id < warp_size then"),
        (10.0, 150.0, 380.0, 162.0, "3:   for i from 0 to window - 1 do"),
        (10.0, 165.0, 400.0, 177.0, "4:     int32 vote = vote_bits[thread_id * window + i]"),
        (10.0, 180.0, 360.0, 192.0, "5:     int32 bidders = __ballot(vote)"),
    ]
    merged = _merge_page_blocks(blocks, min_block_chars=50)
    assert len(merged) == 2
    assert "Algorithm 2" in merged[0][0]
    body = merged[1][0]
    assert "1: int32 mask" in body
    assert "__ballot" in body
