"""Numbering service (Q360-S8-02): atomic, concurrency-safe sequence
increment. ART-012 V024's `numbering_sequence` table is generic
(`sequence_code`/`period_key`/`prefix`/`suffix`) — the actual numbering
*policy* (which prefix, whether to reset per year, how many digits) is
OD-007/OD-008, genuinely open (see DECISIONS_TAKEN.md#S08-DOCUMENT-001).
This module only guarantees "no duplication in concurrency" (Q360-S8-02
AC), not a specific business format.
"""
from __future__ import annotations

from django.db import transaction

from apps.foundation.application.context import CurrentTenantProvider
from apps.quote.infrastructure.models import NumberingSequence


def next_value(*, sequence_code: str, period_key: str, prefix: str | None = None, suffix: str | None = None) -> str:
    """Atomically increments (or creates) the counter identified by
    `(tenant, sequence_code, period_key)` and returns the formatted
    number. `select_for_update` (row lock inside a transaction) is used
    instead of a bare `F('current_value') + 1` update because the
    formatted return value needs the post-increment number in the same
    call — a blind UPDATE cannot hand that back atomically, and a
    read-then-write without a lock would allow two concurrent requests to
    read the same value (Q360-S8-02 AC: "Sem duplicação em concorrência")."""
    tenant_id = CurrentTenantProvider.require()
    with transaction.atomic():
        sequence, _ = NumberingSequence.objects.select_for_update().get_or_create(
            tenant_id=tenant_id.value,
            sequence_code=sequence_code,
            period_key=period_key,
            defaults={"prefix": prefix, "suffix": suffix},
        )
        sequence.current_value += 1
        sequence.row_version += 1
        sequence.save(update_fields=["current_value", "row_version", "updated_at"])
        value = sequence.current_value
        resolved_prefix = sequence.prefix or ""
        resolved_suffix = sequence.suffix or ""
    return f"{resolved_prefix}{value}{resolved_suffix}"


_CONTINUOUS_PERIOD_KEY = "ALL"


def next_continuous_value(*, sequence_code: str, prefix: str | None = None, suffix: str | None = None) -> str:
    """One counter per tenant that never resets. `quote_number`,
    `policy_number` and `document_number` are unique **per tenant** (no year
    in the unique index — `uq_quote_number`, `uq_policy_number`,
    `uq_document_number`), so a counter keyed by year (`next_value` with
    `period_key=<year>`) restarts at 1 on the first quote/policy of a new
    year and collides with a number already issued — which every renewal
    effective in the following year would hit.

    The first call seeds the counter from the highest value already issued
    under the old per-year keys, so numbering carries on without gaps or
    duplicates (the number *format* is unchanged: `COT-12`, `APO-3`)."""
    from django.db.models import Max

    tenant_id = CurrentTenantProvider.require()
    with transaction.atomic():
        existing = NumberingSequence.objects.select_for_update().filter(
            sequence_code=sequence_code, period_key=_CONTINUOUS_PERIOD_KEY
        ).first()
        if existing is None:
            seed = (
                NumberingSequence.objects.filter(sequence_code=sequence_code).aggregate(m=Max("current_value"))["m"] or 0
            )
            existing = NumberingSequence.objects.create(
                tenant_id=tenant_id.value,
                sequence_code=sequence_code,
                period_key=_CONTINUOUS_PERIOD_KEY,
                current_value=seed,
                prefix=prefix,
                suffix=suffix,
            )
        existing.current_value += 1
        existing.row_version += 1
        existing.save(update_fields=["current_value", "row_version", "updated_at"])
        return f"{existing.prefix or ''}{existing.current_value}{existing.suffix or ''}"
