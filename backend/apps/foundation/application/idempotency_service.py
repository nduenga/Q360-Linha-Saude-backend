"""IdempotencyService — transactional idempotency for mutation endpoints.

ART-006 marks every mutation endpoint that is not safe/replayable with a
required `Idempotency-Key` header (see `components/parameters/IdempotencyKey`
and each path's parameter list). This service backs the middleware that
enforces that header: a successful request is recorded together with its
response body, and an identical (key, operation, tenant, body) replay
receives that exact response without re-executing the view. A replay that
reuses the same key with a *different* body receives 409 `IDEMP-REPLAY`
(ProblemDetail) per ART-006's error catalog.

Persisted rows live in `idempotency_record` (ART-012 V025, `managed=False`
ORM model in `infrastructure/models.py`). The record expires 24h after
creation, matching the pragmatic TTL chosen for V1 (no approved document
pins one, and 24h is long enough to catch every realistic retry window
while preventing unbounded table growth).

All queries here use `IdempotencyRecord.all_tenants` (the explicit
cross-tenant escape hatch, not the default tenant-scoped manager): this
service runs from `IdempotencyMiddleware`, which executes before DRF's own
authentication has necessarily bound a tenant (e.g. a missing/invalid
bearer token). Tenant scoping is instead enforced explicitly via the
`tenant_id` filter/column on every call, never implicitly. Do not weaken
`TenantScopedManager` itself to accommodate this — that manager backs every
other business model and must stay fail-closed (DOC-001 s20).
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.foundation.domain.problem import DomainProblem
from apps.foundation.infrastructure.models import IdempotencyRecord


class IdempotencyReplayError(DomainProblem):
    http_status = 409
    problem_code = "IDEMP-REPLAY"


class IdempotencyMissingKeyError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


_EXPIRES_AFTER = timedelta(hours=24)
_IN_PROGRESS_POLL_ATTEMPTS = 3
_IN_PROGRESS_POLL_DELAY = 0.05


@dataclass
class IdempotencyBeginResult:
    started_new: bool
    replayed_response: dict[str, Any] | None = None
    replayed_status: int | None = None
    record_id: uuid.UUID | None = None


def compute_request_hash(
    *,
    method: str,
    path: str,
    raw_body: bytes,
    tenant_id: str,
) -> str:
    payload = f"{method.upper()}|{path}|{tenant_id}|".encode("utf-8") + raw_body
    return hashlib.sha256(payload).hexdigest()


class IdempotencyService:
    def begin(
        self,
        *,
        idempotency_key: str,
        operation_code: str,
        request_hash: str,
        tenant_id: uuid.UUID,
    ) -> IdempotencyBeginResult:
        expires_at = timezone.now() + _EXPIRES_AFTER
        try:
            with transaction.atomic():
                record = IdempotencyRecord.all_tenants.create(
                    tenant_id=tenant_id,
                    idempotency_key=idempotency_key,
                    operation_code=operation_code,
                    request_hash=request_hash,
                    status="IN_PROGRESS",
                    expires_at=expires_at,
                )
            return IdempotencyBeginResult(started_new=True, record_id=record.id)
        except IntegrityError:
            pass

        import time

        for _attempt in range(_IN_PROGRESS_POLL_ATTEMPTS):
            existing = (
                IdempotencyRecord.all_tenants.filter(
                    tenant_id=tenant_id,
                    idempotency_key=idempotency_key,
                    operation_code=operation_code,
                )
                .order_by("-created_at")
                .first()
            )
            if existing is None:
                time.sleep(_IN_PROGRESS_POLL_DELAY)
                continue
            if existing.status == "COMPLETED":
                if existing.request_hash != request_hash:
                    raise IdempotencyReplayError(
                        f"Idempotency-Key '{idempotency_key}' already used with a different payload"
                    )
                return IdempotencyBeginResult(
                    started_new=False,
                    replayed_response=existing.response_body_json,
                    replayed_status=existing.response_status,
                    record_id=existing.id,
                )
            if existing.status == "FAILED":
                if existing.request_hash != request_hash:
                    raise IdempotencyReplayError(
                        f"Idempotency-Key '{idempotency_key}' already used with a different payload"
                    )
                return IdempotencyBeginResult(started_new=True, record_id=existing.id)
            if existing.status == "IN_PROGRESS":
                time.sleep(_IN_PROGRESS_POLL_DELAY)
                continue
            break

        existing = (
            IdempotencyRecord.all_tenants.filter(
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                operation_code=operation_code,
            )
            .order_by("-created_at")
            .first()
        )
        if existing is not None and existing.status == "IN_PROGRESS":
            raise IdempotencyReplayError(
                f"Idempotency-Key '{idempotency_key}' is already being processed; try again shortly"
            )
        return IdempotencyBeginResult(started_new=True, record_id=None)

    def complete(
        self,
        *,
        record_id: uuid.UUID,
        response_status: int,
        response_body_json: dict[str, Any] | None,
        resource_id: str | None = None,
    ) -> None:
        if record_id is None:
            return
        IdempotencyRecord.all_tenants.filter(id=record_id).update(
            status="COMPLETED",
            response_status=response_status,
            response_body_json=response_body_json,
            resource_id=resource_id,
            completed_at=timezone.now(),
        )

    def fail(
        self,
        *,
        record_id: uuid.UUID,
        response_status: int | None = None,
        response_body_json: dict[str, Any] | None = None,
    ) -> None:
        if record_id is None:
            return
        IdempotencyRecord.all_tenants.filter(id=record_id).update(
            status="FAILED",
            response_status=response_status,
            response_body_json=response_body_json,
        )


_idempotency_service = IdempotencyService()


def get_idempotency_service() -> IdempotencyService:
    return _idempotency_service
