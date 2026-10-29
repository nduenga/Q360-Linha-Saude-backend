"""Fecha a vigência terminada, sem depender do instante em que o cron corre."""
from django.core.management.base import BaseCommand

from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role
from apps.foundation.domain.scopes import Scope
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.models import Tenant
from apps.policy.application.lifecycle_service import expire_policies


class Command(BaseCommand):
    help = "Marca como EXPIRED as apólices ativas cujo fim de vigência já passou."

    def handle(self, *args, **options):
        total = 0
        for tenant in Tenant.objects.all():
            token = CurrentActorProvider.bind(Actor(
                actor_id="system-scheduler", tenant_id=TenantId(tenant.id), actor_type="SYSTEM",
                roles=frozenset({Role.ADMIN}), scopes=frozenset({Scope.READ, Scope.WRITE}),
            ))
            try:
                total += expire_policies()
            finally:
                CurrentActorProvider.reset(token)
        self.stdout.write(self.style.SUCCESS(f"Done. {total} policy(ies) expired."))
