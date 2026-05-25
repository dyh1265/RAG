"""Apply conformity validation to a QueryResponse."""

from __future__ import annotations

from phases.phase_04_taxonomy_generation.validation.conformity_validator import ConformityValidator
from shared.models import QueryResponse

_validator: ConformityValidator | None = None


def _get_validator() -> ConformityValidator:
    global _validator
    if _validator is None:
        _validator = ConformityValidator()
    return _validator


def apply_conformity_check(
    response: QueryResponse,
    *,
    block_forbidden: bool = False,
) -> QueryResponse:
    """Run taxonomy conformity check and attach results to response metadata."""
    validator = _get_validator()
    contexts = [ctx.chunk.content for ctx in response.retrieved_contexts]
    result = validator.validate(response.query, response.answer, contexts)

    metadata = dict(response.metadata)
    metadata["conformity"] = result.to_metadata()

    answer = response.answer
    if block_forbidden and validator.should_block(result):
        answer = "[BLOCKED — taxonomy violation]"
        metadata["conformity_blocked"] = True

    return response.model_copy(update={"answer": answer, "metadata": metadata})


__all__ = ["apply_conformity_check"]
