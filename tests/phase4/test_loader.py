"""Tests for taxonomy loader."""

from __future__ import annotations

import pytest

pytest.importorskip("rdflib")

from phases.phase_04_taxonomy_generation.ontology.loader import load_taxonomy


def test_load_classification_taxonomy():
    tax = load_taxonomy()
    assert "PUBLIC" in tax.allowed_labels
    assert "CONFIDENTIAL" in tax.allowed_labels
    assert "SECRET-TOP-SECRET" in tax.forbidden_labels
