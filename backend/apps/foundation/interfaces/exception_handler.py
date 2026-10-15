"""Error envelope for the Q360 API — Q360-MVP-ART-006 `ProblemDetail` schema
and `x-q360-error-catalog`, copied verbatim (DOC-004 s2: "ART-006 será
autoridade final do HTTP").

`_CODE_BY_EXCEPTION` maps generic DRF exception types to one of ART-006's
already-approved `code` values; `_TITLES` is ART-006's catalog descriptions
verbatim. Do not invent a `code` that is not in ART-006's
`x-q360-error-catalog` — if a new situation needs one, that is a Change
Request against ART-006 (DOC-000 s12), not a local addition here.
"""
from __future__ import annotations

from django.http import Http404
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.foundation.domain.problem import DomainProblem
from apps.foundation.interfaces.middleware import get_correlation_id

# ART-006 x-q360-error-catalog titles, verbatim. Codes reached only via a
# module's own DomainProblem subclass (VERSION-CONFLICT, CONFLICT, ...)
# are listed here too so every title stays in one place regardless of
# which module raises them.
_TITLES: dict[str, str] = {
    "AUTH-401": "Não autenticado",
    "AUTH-403": "Sem autorização",
    "SEC-403": "Violação de segurança/tenant/four-eyes",
    "VALIDATION-400": "Pedido inválido",
    "VERSION-CONFLICT": "Conflito de versão",
    "QUOTE-STATE": "Transição inválida",
    "PRICING-CONFIG": "Configuração de pricing ausente/inválida",
    "PRICING-FAILED": "Falha de cálculo",
    "IDEMP-REPLAY": "Chave de idempotência reutilizada com conteúdo diferente",
    "NOT-FOUND": "Recurso não encontrado",
    "CONFLICT": "Conflito genérico",
    "RATE-LIMIT": "Limite excedido",
    # Customer portal (ROADMAP_PORTAL_CLIENTE.md) — a new actor/contract
    # outside ART-006's catalog, not a Change Request against it.
    "PORTAL-LOCKED": "Conta temporariamente bloqueada",
    "PORTAL-NO-EMAIL": "Sem email registado",
    # DECISIONS_TAKEN.md#S09-POLICY-001/Fase 6: renamed from
    # PORTAL-QUOTE-NOT-FOUND — login resolves by Policy.policyNumber now.
    "PORTAL-POLICY-NOT-FOUND": "Apólice não encontrada",
    "PORTAL-REGISTRATION-MISMATCH": "Número de registo não corresponde",
    # apps.policy (DECISIONS_TAKEN.md#S09-POLICY-001/003) — postdates
    # ART-006 entirely, same posture as PORTAL-*/STAFF-* above.
    "POLICY-STATE": "Transição inválida",
    # apps.staff_accounts — self-hosted staff identity (replaces the
    # external Auth0 IdP), same posture: a new contract, not a CR.
    "STAFF-LOCKED": "Conta temporariamente bloqueada",
    # apps.business_config — configuração de tarifação por produto (grupos de
    # opções, campos e fórmulas): dados da cotação em falta ou que não batem.
    "PRODUCT-SETUP-INPUT": "Dados do produto em falta ou inválidos",
}

_CODE_BY_EXCEPTION: dict[type[Exception], str] = {
    NotAuthenticated: "AUTH-401",
    AuthenticationFailed: "AUTH-401",
    PermissionDenied: "AUTH-403",
    ValidationError: "VALIDATION-400",
    NotFound: "NOT-FOUND",
    # get_object_or_404() raises the plain Django exception, not DRF's
    # NotFound. drf_exception_handler() converts it to a 404 Response
    # internally, but `exc` here is still the original Http404 — map it
    # too, or a NOT-FOUND response would silently lose `code`/`correlationId`.
    Http404: "NOT-FOUND",
    Throttled: "RATE-LIMIT",
}


def q360_exception_handler(exc, context):
    if isinstance(exc, DomainProblem):
        return _problem_response(exc.problem_code, exc.http_status, str(exc))

    response = drf_exception_handler(exc, context)
    if response is None:
        return None  # Unmapped (5xx) exception: Django's default handling applies.

    code = _CODE_BY_EXCEPTION.get(type(exc))
    if code is None:
        return response

    field_errors = _field_errors(exc.detail) if isinstance(exc, ValidationError) else None
    detail = _readable(field_errors) if field_errors else str(exc)
    return _problem_response(code, response.status_code, detail, field_errors=field_errors)


def _readable(field_errors: list[dict[str, str]]) -> str:
    """Resumo em português do que falhou, em vez da representação técnica do DRF."""
    parts = []
    for error in field_errors:
        field = error["field"]
        parts.append(error["message"] if field == "non_field_errors" else f"{field}: {error['message']}")
    return " | ".join(parts)


def _field_errors(detail, prefix: str = "") -> list[dict[str, str]]:
    """ART-006 `ProblemDetail.fieldErrors`: one `{field, code, message}` per
    invalid field, nested fields as `parent.child` / `list[0].child`."""
    out: list[dict[str, str]] = []
    if isinstance(detail, dict):
        for key, value in detail.items():
            out += _field_errors(value, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(detail, list):
        for index, item in enumerate(detail):
            if isinstance(item, (dict, list)):
                out += _field_errors(item, f"{prefix}[{index}]")
            else:
                out.append({"field": prefix or "non_field_errors", "code": getattr(item, "code", "invalid"), "message": str(item)})
    else:
        out.append({"field": prefix or "non_field_errors", "code": getattr(detail, "code", "invalid"), "message": str(detail)})
    return out


def _problem_response(code: str, status_code: int, detail: str, *, field_errors=None) -> Response:
    problem = {
        "title": _TITLES[code],
        "status": status_code,
        "code": code,
        "detail": detail,
        "correlationId": get_correlation_id() or "",
    }
    if field_errors:
        problem["fieldErrors"] = field_errors
    return Response(problem, status=status_code, content_type="application/problem+json")
