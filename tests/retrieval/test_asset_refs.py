"""Tests for table/figure label parsing and matching."""

from __future__ import annotations

from backend.retrieval.asset_refs import (
    content_matches_asset_label,
    parse_asset_reference,
)


def test_parse_table_and_figure_queries():
    assert parse_asset_reference("table 1") == ("table", "1")
    assert parse_asset_reference("what is in Table 2?") == ("table", "2")
    assert parse_asset_reference("figure 2") == ("figure", "2")
    assert parse_asset_reference("Fig. 3") == ("figure", "3")
    assert parse_asset_reference("Algorithm 2") == ("algorithm", "2")
    assert parse_asset_reference("alg. 1") == ("algorithm", "1")


def test_content_matches_roman_table_label():
    body = "As shown in Table I, the UMQ length varies by rank."
    assert content_matches_asset_label(body, "table", "1")
    assert not content_matches_asset_label(body, "table", "2")


def test_content_matches_figure_label():
    caption = "Figure 2. Maximum length of each rank of the UMQ for different applications."
    assert content_matches_asset_label(caption, "figure", "2")
