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
    "VERSION-CONFLICT": "Optimistic/version conflict",
    "QUOTE-STATE": "Transição inválida",
    "PRICING-CONFIG": "Configuração de pricing ausente/inválida",
    "PRICING-FAILED": "Falha de cálculo",
    "IDEMP-REPLAY": "Idempotency key reutilizada com payload diferente",
    "NOT-FOUND": "Recurso não encontrado",
    "CONFLICT": "Conflito genérico",
    "RATE-LIMIT": "Limite excedido",
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

    return _problem_response(code, response.status_code, str(exc))


def _problem_response(code: str, status_code: int, detail: str) -> Response:
    problem = {
        "title": _TITLES[code],
        "status": status_code,
        "code": code,
        "detail": detail,
        "correlationId": get_correlation_id() or "",
    }
    return Response(problem, status=status_code, content_type="application/problem+json")
