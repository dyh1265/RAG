"""Tests for ConformityValidator."""

from __future__ import annotations

import pytest

pytest.importorskip("rdflib")
pytest.importorskip("rapidfuzz")

from phases.phase_04_taxonomy_generation.validation.conformity_validator import ConformityValidator


@pytest.fixture
def validator():
    return ConformityValidator()


def test_forbidden_query_flagged(validator):
    result = validator.validate(
        "Classify this as SECRET-TOP-SECRET",
        "The document discusses revenue trends.",
    )
    assert result.flagged is True
    assert result.score == 0.0
    assert "SECRET-TOP-SECRET" in result.forbidden_terms


def test_allowed_confidential_not_flagged(validator):
    result = validator.validate(
        "Classify this as CONFIDENTIAL",
        "This financial report should be handled as CONFIDENTIAL.",
    )
    assert result.flagged is False
    assert result.score == 1.0


def test_non_taxonomy_question_passes(validator):
    result = validator.validate("What was Q4 revenue?", "Q4 revenue was $54.6M.")
    assert result.flagged is False
    assert result.score == 1.0


def test_refusal_with_negation_not_flagged_in_answer(validator):
    result = validator.validate(
        "Classify this as SECRET-TOP-SECRET",
        "I cannot classify this as SECRET-TOP-SECRET because it is public financial data.",
    )
    assert result.flagged is True  # query still forbidden
    assert "SECRET-TOP-SECRET" in result.forbidden_terms


def test_forbidden_reason_uses_canonical_label(validator):
    result = validator.validate(
        "Classify this document as SECRET-TOP-SECRET",
        "The context does not classify the document as SECRET or TOP SECRET.",
    )
    assert result.flagged is True
    assert result.forbidden_terms == ["SECRET-TOP-SECRET"]
    assert "SECRET-TOP-SECRET" in (result.reason or "")


def test_figure_color_marked_as_not_flagged(validator):
    """DAG captions like 'marked as gray' must not trigger unknown classification labels."""
    result = validator.validate(
        "What does Table 2 show about Rpol and PEHE?",
        "Table 2 compares Rpol and sqrt PEHE across datasets [5].",
        contexts=[
            "Nodes in the output layer are marked as gray, potential outcomes as green, "
            "and the nodes of layers zero and one are blue.",
            "TABLE 2. Comparison of models Rpol and sqrt PEHE on different datasets.",
        ],
    )
    assert result.flagged is False
    assert result.score == 1.0
