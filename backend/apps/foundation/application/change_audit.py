"""Shared helpers for auditable *changes* (before/after/reason).

DOC-001 s19 requires "quem alterou, quando, o que alterou e qual o
impacto" for every relevant configuration/pricing change (requisitos
não funcionais do simulador GTE). `AuditService.record` has no dedicated
columns for it (ART-005 is frozen), so the convention - like `result`/
`reason` already is - lives in `metadata`: `before`, `after`, `reason` and
an optional `impact` dict (e.g. premium delta).
"""
from __future__ import annotations

from typing import Any

from apps.foundation.domain.problem import DomainProblem

MIN_REASON_LENGTH = 10


class ReasonRequiredError(DomainProblem):
    """A change that must be justified (adjustment, rollback, deactivation)
    arrived without a usable `reason`."""

    http_status = 400
    problem_code = "VALIDATION-400"


def require_reason(reason: str | None, *, min_length: int = MIN_REASON_LENGTH) -> str:
    cleaned = (reason or "").strip()
    if len(cleaned) < min_length:
        raise ReasonRequiredError(f"É obrigatória uma justificação ('reason') com pelo menos {min_length} caracteres")
    return cleaned


def change_metadata(
    *,
    before: Any = None,
    after: Any = None,
    reason: str | None = None,
    impact: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"result": "SUCCESS", **extra}
    if before is not None:
        metadata["before"] = before
    if after is not None:
        metadata["after"] = after
    if reason is not None:
        metadata["reason"] = reason
    if impact is not None:
        metadata["impact"] = impact
    return metadata
