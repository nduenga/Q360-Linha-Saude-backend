"""Correlation-ID propagation, idempotency enforcement, and defensive
per-request context cleanup (Q360-S1-01/S1-02, S09 Idempotência).

`CorrelationIdMiddleware`: reads `X-Correlation-Id` from the inbound
request (or generates one), binds it for the request/response lifecycle
so structured logs and AuditService calls can attach it, echoes it back.

`IdempotencyMiddleware`: for views decorated with `@requires_idempotency`,
reads the mandatory `Idempotency-Key` header, hashes the request, and
either (a) runs the view and persists the response, (b) returns a
previously-persisted identical response, or (c) raises 409 IDEMP-REPLAY
when the same key is reused with a different payload.

`ActorContextCleanupMiddleware`: guarantees `CurrentActorProvider` never
leaks across requests handled by the same worker thread.
"""
from __future__ import annotations

import contextvars
import functools
import json
import logging
import threading
import time
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.urls import Resolver404, resolve

CORRELATION_HEADER = "X-Correlation-Id"
_IDEMPOTENCY_HEADER = "Idempotency-Key"
_IDEMPOTENCY_ATTR = "_q360_requires_idempotency"
# ART-006 only ever declares IdempotencyKey on mutating operations. The
# decorator is applied at the class level (several views mix a GET list
# with a POST create on the same class), so the middleware must not
# enforce it for safe/read methods sharing that class.
_IDEMPOTENCY_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "q360_correlation_id", default=None
)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def requires_idempotency(view_func_or_cls):
    """Mark a DRF view or function view as requiring Idempotency-Key.

    Applied to a class-based view, it sets the marker on the class so the
    middleware can see it regardless of which HTTP method (post/put/patch/
    delete) dispatches. Applied to a function view, the marker lives on
    the function itself.
    """
    if isinstance(view_func_or_cls, type):
        setattr(view_func_or_cls, _IDEMPOTENCY_ATTR, True)
        return view_func_or_cls

    @functools.wraps(view_func_or_cls)
    def wrapper(*args, **kwargs):
        return view_func_or_cls(*args, **kwargs)

    setattr(wrapper, _IDEMPOTENCY_ATTR, True)
    return wrapper


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


class IdempotencyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in _IDEMPOTENCY_SAFE_METHODS:
            return self.get_response(request)

        # `resolver_match` is assigned after ordinary new-style middleware
        # starts on some Django code paths. Resolve explicitly so this guard
        # cannot silently become a no-op (the old implementation did exactly
        # that for APIClient and production requests alike).
        resolver_match = getattr(request, "resolver_match", None)
        if resolver_match is None:
            try:
                resolver_match = resolve(request.path_info)
            except Resolver404:
                return self.get_response(request)
        requires = False
        if resolver_match is not None:
            view_class = getattr(resolver_match.func, "view_class", None)
            view_func = resolver_match.func
            if view_class is not None and getattr(view_class, _IDEMPOTENCY_ATTR, False):
                requires = True
            elif getattr(view_func, _IDEMPOTENCY_ATTR, False):
                requires = True

        if not requires or not settings.IDEMPOTENCY_REQUIRED:
            return self.get_response(request)

        idempotency_key = request.headers.get(_IDEMPOTENCY_HEADER)
        if not idempotency_key:
            from apps.foundation.application.idempotency_service import (
                IdempotencyMissingKeyError,
            )

            return self._problem_response(
                code=IdempotencyMissingKeyError.problem_code,
                status=IdempotencyMissingKeyError.http_status,
                detail="Idempotency-Key header is required for this operation",
            )

        from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
        from apps.foundation.infrastructure.jwt_actor_adapter import InvalidTokenError, JwtActorAdapter
        from apps.foundation.application.idempotency_service import (
            compute_request_hash,
            get_idempotency_service,
        )

        # DRF authenticates lazily inside the view. Resolve the bearer token
        # here as well so the idempotency key is partitioned by the real
        # tenant, rather than by a shared anonymous placeholder.
        if CurrentTenantProvider.get() is None:
            from rest_framework.authentication import get_authorization_header

            header = get_authorization_header(request).decode("utf-8")
            if header.lower().startswith("bearer "):
                try:
                    CurrentActorProvider.bind(JwtActorAdapter().resolve(header[7:].strip()))
                except InvalidTokenError:
                    pass

        method = request.method
        path = request.path_info or request.path
        raw_body = self._raw_body(request)
        tenant_id = CurrentTenantProvider.get()
        tenant_str = str(tenant_id.value) if tenant_id is not None else ""
        request_hash = compute_request_hash(
            method=method, path=path, raw_body=raw_body, tenant_id=tenant_str
        )
        operation_code = self._operation_code(resolver_match)

        service = get_idempotency_service()
        try:
            begin_result = service.begin(
                idempotency_key=idempotency_key,
                operation_code=operation_code,
                request_hash=request_hash,
                tenant_id=tenant_id.value if tenant_id else uuid.UUID(
                    "00000000-0000-0000-0000-000000000000"
                ),
            )
        except Exception as exc:
            if not hasattr(exc, "problem_code"):
                raise
            # Bug fix (found while investigating DECISIONS_TAKEN.md#S09-
            # IDEMPOTENCY-001): this branch returns without ever calling
            # `self.get_response(request)`, so `ActorContextCleanupMiddleware`
            # (deeper in MIDDLEWARE, only runs *inside* get_response) never
            # executes for it - the actor this middleware bound above (line
            # ~143) would otherwise stay bound into whatever request this
            # worker thread/task handles next, corrupting that next
            # request's idempotency tenant scoping (its own `if
            # CurrentTenantProvider.get() is None` check above would find a
            # stale non-None value and skip resolving its own token). Same
            # fix applied to the replay short-circuit below.
            CurrentActorProvider.bind(None)
            return self._problem_response(
                code=exc.problem_code,
                status=exc.http_status,
                detail=str(exc),
            )

        if not begin_result.started_new and begin_result.replayed_response is not None:
            CurrentActorProvider.bind(None)
            return JsonResponse(
                begin_result.replayed_response,
                status=begin_result.replayed_status or 200,
            )

        record_id = begin_result.record_id
        try:
            response = self.get_response(request)
        except Exception as exc:
            response_status = 500
            response_body = None
            if hasattr(exc, "http_status"):
                response_status = exc.http_status
            service.fail(
                record_id=record_id,
                response_status=response_status,
                response_body_json=response_body,
            )
            raise

        response_status = getattr(response, "status_code", 200)
        response_body = self._response_body_for_persistence(response)
        resource_id = self._extract_resource_id(response_body)
        service.complete(
            record_id=record_id,
            response_status=response_status,
            response_body_json=response_body,
            resource_id=resource_id,
        )
        return response

    @staticmethod
    def _raw_body(request) -> bytes:
        raw = getattr(request, "_body", None)
        if raw is not None:
            return raw if isinstance(raw, bytes) else b""
        try:
            raw = request.read()
        except Exception:
            return b""
        request._body = raw
        try:
            request.seek(0)
        except Exception:
            pass
        return raw if isinstance(raw, bytes) else b""

    @staticmethod
    def _operation_code(resolver_match) -> str:
        view_class = getattr(resolver_match.func, "view_class", None)
        if view_class is not None:
            return f"{view_class.__module__}.{view_class.__qualname__}"
        return f"{resolver_match.func.__module__}.{resolver_match.func.__qualname__}"

    @staticmethod
    def _response_body_for_persistence(response) -> dict | None:
        data = getattr(response, "data", None)
        if data is None:
            return None
        # Always round-trip through JSON, dicts included: serializer output
        # can still hold UUID/Decimal/date objects (e.g. SerializerMethodField
        # values) that the JSONField below cannot encode, which used to turn
        # an already-successful request into a 500 at persistence time.
        try:
            serialized = json.loads(json.dumps(data, default=str))
            if isinstance(serialized, dict):
                return serialized
            return {"items": serialized} if isinstance(serialized, list) else {"value": serialized}
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_resource_id(body: dict | None) -> str | None:
        if not body or not isinstance(body, dict):
            return None
        for key in ("id", "quoteId", "memberId", "productId", "versionId"):
            value = body.get(key)
            if value is not None:
                return str(value)
        return None

    @staticmethod
    def _problem_response(*, code: str, status: int, detail: str) -> JsonResponse:
        titles = {
            "VALIDATION-400": "Pedido inválido",
            "IDEMP-REPLAY": "Idempotency key reutilizada com payload diferente",
        }
        return JsonResponse(
            {
                "title": titles.get(code, "Pedido inválido"),
                "status": status,
                "code": code,
                "detail": detail,
                "correlationId": get_correlation_id() or "",
            },
            status=status,
            content_type="application/problem+json",
        )


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


class RequestTelemetryMiddleware:
    """Emit a low-cardinality request span without exposing PII.

    The implementation delegates to the optional observability module.  It
    intentionally records only HTTP method, route and status; headers, query
    parameters and request bodies are never copied into telemetry.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from apps.foundation.observability import request_span

        with request_span(request.method, request.path_info) as span:
            response = self.get_response(request)
            span.set_status_code(getattr(response, "status_code", 500))
            return response


class RateLimitMiddleware:
    """Thread-safe fixed-window guard for direct API deployment.

    It is intentionally a bounded in-process fallback, not a replacement for
    a distributed gateway limiter.  A production deployment using multiple
    processes should configure its edge/WAF and disable this guard with a
    zero request limit.  Tenant is part of the key only after authentication;
    otherwise the remote address keeps abusive unauthenticated traffic from
    bypassing the limit.
    """

    _lock = threading.Lock()
    _buckets: dict[tuple[str, int], int] = {}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        limit = settings.RATE_LIMIT_REQUESTS
        if limit <= 0 or request.path_info in settings.RATE_LIMIT_EXEMPT_PATHS:
            return self.get_response(request)

        window = max(1, settings.RATE_LIMIT_WINDOW_SECONDS)
        now = time.monotonic()
        bucket = int(now // window)
        actor = getattr(getattr(request, "user", None), "actor", None)
        identity = str(actor.tenant_id) if actor is not None else (request.META.get("REMOTE_ADDR") or "unknown")
        key = (identity, bucket)
        with self._lock:
            # Drop earlier buckets to keep memory bounded in long-lived
            # workers. This remains O(number of active identities).
            self._buckets = {k: v for k, v in self._buckets.items() if k[1] >= bucket - 1}
            count = self._buckets.get(key, 0) + 1
            self._buckets[key] = count

        if count > limit:
            return JsonResponse(
                {
                    "title": "Limite excedido",
                    "status": 429,
                    "code": "RATE-LIMIT",
                    "detail": "Too many requests in the current time window.",
                    "correlationId": get_correlation_id() or "",
                },
                status=429,
                content_type="application/problem+json",
            )
        return self.get_response(request)
