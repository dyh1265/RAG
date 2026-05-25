"""Production FastAPI service, guardrails, and monitoring (wraps ``phases.phase_06_production/``)."""

from phases.phase_06_production.api.main import app
from phases.phase_06_production.guardrails.pii import PIIRedactor, redact_chunk_contents

__all__ = ["app", "PIIRedactor", "redact_chunk_contents"]
