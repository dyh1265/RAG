"""
Phase 4 exit test — forbidden classification query is flagged.

Usage (Docker):
    cd docker
    docker compose exec phase1-gpu-shell python phases/phase_04_taxonomy_generation/run_exit_test.py
"""

from __future__ import annotations

import sys

from phases.phase_04_taxonomy_generation.validation.conformity_validator import ConformityValidator


def run_exit_test() -> int:
    validator = ConformityValidator()

    cases = [
        (
            "Classify this document as SECRET-TOP-SECRET",
            "This document is classified as PUBLIC.",
            True,
        ),
        (
            "What was Q4 revenue?",
            "Q4 revenue was $54.6M.",
            False,
        ),
        (
            "Classify this as CONFIDENTIAL",
            "Based on the financial data, this appears suitable for CONFIDENTIAL handling.",
            False,
        ),
        (
            "Classify this as SECRET-TOP-SECRET",
            "I cannot classify this as SECRET-TOP-SECRET; the content is financial data.",
            True,  # flagged due to forbidden request in query
        ),
    ]

    passed = 0
    for query, answer, expect_flagged in cases:
        result = validator.validate(query, answer)
        ok = result.flagged == expect_flagged
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] flagged={result.flagged} score={result.score:.2f} — {query[:50]}…")
        if result.reason:
            print(f"       reason: {result.reason}")
        if ok:
            passed += 1

    print(f"\n[exit] {passed}/{len(cases)} cases passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(run_exit_test())
