"""Q360-S8-03 — EXPIRE transitions (ART-009 QT-011..014), actor "System
Scheduler" ("No user-supplied actor", Commands & Authority sheet).

No background task queue exists in this stack (DOC-002 s4 Premissas: "no
messaging without a real consumer") — this command is meant to be invoked
by an external, deterministic, testable scheduler (cron / Windows Task
Scheduler / a Kubernetes CronJob in deployment), not by this codebase
itself. Idempotent: re-running it only affects quotes that are still due.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role
from apps.foundation.domain.scopes import Scope
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.models import Tenant
from apps.quote.application.quote_service import CANCELLABLE_QUOTE_STATUSES, expire_quote
from apps.quote.infrastructure.models import Quote

_SYSTEM_ACTOR_ID = "system-scheduler"


class Command(BaseCommand):
    help = "Expire quotes whose validUntil has elapsed, across every tenant (Q360-S8-03)."

    def handle(self, *args, **options):
        total_expired = 0
        for tenant in Tenant.objects.all():
            actor = Actor(
                actor_id=_SYSTEM_ACTOR_ID,
                tenant_id=TenantId(tenant.id),
                roles=frozenset({Role.ADMIN}),
                scopes=frozenset({Scope.READ, Scope.WRITE}),
                actor_type="SYSTEM",
            )
            token = CurrentActorProvider.bind(actor)
            try:
                # Propostas de endosso aprovadas têm prazo próprio de aceitação
                # (`expire_endorsement_offers`), não a validade da cotação.
                due = Quote.objects.filter(status__in=CANCELLABLE_QUOTE_STATUSES, valid_until__isnull=False).exclude(
                    quote_type="ENDORSEMENT", status="APPROVED"
                )
                for quote in list(due):
                    if expire_quote(quote=quote) is not None:
                        total_expired += 1
                        self.stdout.write(f"Expired quote {quote.id} (tenant {tenant.code})")
            finally:
                CurrentActorProvider.reset(token)

        self.stdout.write(self.style.SUCCESS(f"Done. {total_expired} quote(s) expired."))
