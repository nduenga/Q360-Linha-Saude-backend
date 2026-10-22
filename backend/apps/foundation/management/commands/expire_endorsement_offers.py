"""Expira as propostas de endosso de inclusão cujo prazo de aceitação do
cliente (`policy.endorsements.acceptance_days`) já terminou. Idempotente;
pensado para um agendador externo (cron, uma vez por dia), como
`expire_quotes`. As consultas e respostas também expiram a pedido."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role
from apps.foundation.domain.scopes import Scope
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.models import Tenant
from apps.policy.application.endorsement_service import expire_offers


class Command(BaseCommand):
    help = "Expira as propostas de endosso fora do prazo de aceitação (todos os inquilinos)."

    def handle(self, *args, **options):
        total = 0
        for tenant in Tenant.objects.all():
            actor = Actor(
                actor_id="system-scheduler",
                tenant_id=TenantId(tenant.id),
                roles=frozenset({Role.ADMIN}),
                scopes=frozenset({Scope.READ, Scope.WRITE}),
                actor_type="SYSTEM",
            )
            token = CurrentActorProvider.bind(actor)
            try:
                total += expire_offers()
            finally:
                CurrentActorProvider.reset(token)
        self.stdout.write(self.style.SUCCESS(f"Done. {total} endorsement offer(s) expired."))
