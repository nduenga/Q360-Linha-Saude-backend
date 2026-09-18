"""`manage.py dispatch_outbox` — batch dispatcher for the Transactional Outbox.

Two modes:
  * `--once`    : run a single batch pass, then exit. Use for cron/one-shot.
  * `--interval N`: continuous loop, sleep N seconds between passes. Use
                    for a persistent worker process (similar to Celery beat
                    but without a broker dependency — matches the stack's
                    "no task queue" posture, same as `expire_quotes`).

Each pass:
  1. `SELECT … LIMIT 50 FOR UPDATE SKIP LOCKED` reclaimable rows
     (PENDING / FAILED past next_attempt_at).
  2. For each row: PROCESSING → call publisher.publish(envelope).
  3. Success → status=PUBLISHED + published_at.
     Failure → attempts++, last_error_safe (truncated 2KB, PII-scrubbed),
                next_attempt_at by short backoff; FAILED after 5 attempts.

The default publisher (ValidatingNoopPublisher) never talks to a real broker
(spec Non-Goals). Plug a real RabbitMQ/Kafka adapter into `OutboxService`
in a deployment-specific bootstrap if needed.
"""
from __future__ import annotations

import time
import traceback
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.foundation.application.outbox_service import (
    _backoff_next_attempt,
    get_outbox_service,
)
from apps.foundation.infrastructure.models import OutboxEvent

_BATCH_LIMIT = 50
_MAX_ATTEMPTS = 5
_MAX_ERROR_LEN = 2048
_PRODUCER_NAME = "dispatch_outbox"
_FORBIDDEN_IN_ERROR_LC = {
    "password",
    "secret",
    "authorization",
    "access_token",
    "refresh_token",
    "jwt",
    "api_key",
    "token",
}


def _sanitise_error(text: str) -> str:
    """Remove raw payload/token content from an error string before storing.

    We truncate to _MAX_ERROR_LEN and redact lines/words that contain
    obviously forbidden substring keys. A leak of the raw business payload
    (which could contain PII like member names) into `last_error_safe` is
    prevented by never including the envelope/payload body itself; we keep
    only exception class, message, and a truncated stack trace.
    """
    lines = []
    for raw in text.splitlines()[:64]:
        lower = raw.lower()
        if any(forbidden in lower for forbidden in _FORBIDDEN_IN_ERROR_LC):
            lines.append("[redacted]")
            continue
        lines.append(raw)
    joined = "\n".join(lines)
    if len(joined) > _MAX_ERROR_LEN:
        joined = joined[: _MAX_ERROR_LEN - 3] + "..."
    return joined


def models_Q_next_attempt(now):
    return (
        Q(next_attempt_at__isnull=True)
        | Q(next_attempt_at__lte=now)
    )


class Command(BaseCommand):
    help = "Dispatch pending outbox events via the configured publisher."

    def add_arguments(self, parser):  # type: ignore[override]
        parser.add_argument(
            "--once",
            action="store_true",
            dest="once",
            help="Run exactly one batch pass and exit (default: loop)",
        )
        parser.add_argument(
            "--interval",
            type=int,
            dest="interval",
            default=None,
            help="Seconds to sleep between passes. Implies loop mode.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            dest="batch_size",
            default=_BATCH_LIMIT,
            help=f"Rows claimed per pass (default {_BATCH_LIMIT}).",
        )

    def handle(self, *args: Any, **options: Any) -> str | None:
        once: bool = options.get("once") or False
        interval: int | None = options.get("interval")
        batch_size: int = options.get("batch_size") or _BATCH_LIMIT

        loop = not once
        if interval is not None and interval <= 0:
            raise ValueError("--interval must be positive")

        publisher = get_outbox_service().get_publisher()

        while True:
            published, failed, skipped = self._run_one_pass(
                batch_size=batch_size, publisher=publisher
            )
            msg = (
                f"dispatch_outbox: published={published} "
                f"failed_perm={failed} claimed_skipped={skipped}"
            )
            self.stdout.write(msg)

            if not loop:
                break
            sleep_s = interval if interval is not None else 5
            time.sleep(sleep_s)

        return None

    def _run_one_pass(self, *, batch_size: int, publisher: Any) -> tuple[int, int, int]:
        published = 0
        failed_perm = 0
        skipped = 0

        with transaction.atomic():
            now = timezone.now()
            claimable = list(
                OutboxEvent.all_tenants.filter(
                    status__in=["PENDING", "FAILED"],
                )
                .filter(
                    models_Q_next_attempt(now)
                )
                .order_by("occurred_at")
                .select_for_update(skip_locked=True, of=("self",))[:batch_size]
            )
            ids = [e.id for e in claimable]
            if ids:
                OutboxEvent.all_tenants.filter(id__in=ids).update(
                    status="PROCESSING",
                    locked_at=now,
                    locked_by=_PRODUCER_NAME,
                )

        if not claimable:
            return 0, 0, 0

        for event in claimable:
            envelope = event.payload_json if isinstance(event.payload_json, dict) else {}
            try:
                publisher.publish(envelope)
            except Exception as exc:  # noqa: BLE001 — dispatcher must never crash
                raw_err = "".join(traceback.format_exception_only(type(exc), exc))
                sanitised = _sanitise_error(raw_err)
                attempts = event.attempts + 1
                if attempts >= _MAX_ATTEMPTS:
                    new_status = "FAILED"
                    next_attempt = None
                    failed_perm += 1
                else:
                    new_status = "FAILED"
                    next_attempt = _backoff_next_attempt(attempts)
                with transaction.atomic():
                    OutboxEvent.all_tenants.filter(id=event.id).update(
                        status=new_status,
                        attempts=attempts,
                        last_error_safe=sanitised,
                        next_attempt_at=next_attempt,
                        locked_at=None,
                        locked_by=None,
                    )
                continue

            with transaction.atomic():
                OutboxEvent.all_tenants.filter(id=event.id).update(
                    status="PUBLISHED",
                    attempts=event.attempts + 1,
                    published_at=timezone.now(),
                    locked_at=None,
                    locked_by=None,
                )
            published += 1

        return published, failed_perm, skipped
