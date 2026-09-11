"""Correlation-ID propagation and defensive per-request context cleanup
(Q360-S1-01/S1-02: "correlation-id e logs estruturados"; Q360-S1-04: audit
denied access / correlation-id).

`CorrelationIdMiddleware` is the "CorrelationIdFilter" component named in
DOC-004 s6.1: it reads `X-Correlation-Id` from the inbound request (or
generates one), binds it for the request/response lifecycle so structured
logs and AuditService calls can attach it, and echoes it back on the
response.

`ActorContextCleanupMiddleware` guarantees `CurrentActorProvider` (bound by
`JwtActorAuthentication.authenticate`, which runs *inside* `get_response`
since DRF authentication happens during view dispatch, after Django
middleware has already started) never leaks into the next request handled
by the same worker thread — including when the view raises.
"""
from __future__ import annotations

import contextvars
import logging
import uuid

CORRELATION_HEADER = "X-Correlation-Id"

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "q360_correlation_id", default=None
)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


class CorrelationIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        correlation_id = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        token = _correlation_id.set(correlation_id)
        request.correlation_id = correlation_id
        try:
            response = self.get_response(request)
        finally:
            _correlation_id.reset(token)
        response[CORRELATION_HEADER] = correlation_id
        return response


class ActorContextCleanupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from apps.foundation.application.context import CurrentActorProvider

        try:
            response = self.get_response(request)
        finally:
            CurrentActorProvider.bind(None)
        return response


class CorrelationIdLogFilter(logging.Filter):
    """Attaches `correlation_id` to every log record for structured logging."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or "-"
        return True
