"""Tests for table/figure label parsing and matching."""

from __future__ import annotations

from backend.retrieval.asset_refs import (
    content_matches_asset_label,
    normalize_reference_keywords,
    parse_asset_reference,
    parse_page_reference,
)


def test_parse_table_and_figure_queries():
    assert parse_asset_reference("table 1") == ("table", "1")
    assert parse_asset_reference("what is in Table 2?") == ("table", "2")
    assert parse_asset_reference("figure 2") == ("figure", "2")
    assert parse_asset_reference("Fig. 3") == ("figure", "3")
    assert parse_asset_reference("Algorithm 2") == ("algorithm", "2")
    assert parse_asset_reference("alg. 1") == ("algorithm", "1")


def test_normalize_reference_keywords_fixes_typos_before_number():
    assert normalize_reference_keywords("slde 7") == "slide 7"
    assert normalize_reference_keywords("what about figuer2") == "what about figure2"
    assert normalize_reference_keywords("see tabel 3") == "see table 3"
    assert normalize_reference_keywords("on paeg 5") == "on page 5"


def test_normalize_reference_keywords_leaves_prose_untouched():
    # No trailing number → not a structural reference, must not be rewritten.
    assert normalize_reference_keywords("the door slied open") == "the door slied open"
    assert normalize_reference_keywords("a figue of speech") == "a figue of speech"


def test_typo_queries_still_resolve_references():
    assert parse_page_reference("what did the author say about slde 7") == 7
    assert parse_page_reference("explain silde #12") == 12
    assert parse_asset_reference("describe figuer 2") == ("figure", "2")
    assert parse_asset_reference("what is in tabel 1") == ("table", "1")


def test_content_matches_roman_table_label():
    body = "As shown in Table I, the UMQ length varies by rank."
    assert content_matches_asset_label(body, "table", "1")
    assert not content_matches_asset_label(body, "table", "2")


def test_content_matches_figure_label():
    caption = "Figure 2. Maximum length of each rank of the UMQ for different applications."
    assert content_matches_asset_label(caption, "figure", "2")
