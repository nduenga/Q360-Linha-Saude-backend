"""`manage.py migrate_legacy_tariffs --tenant-code X [--dry-run]`

Converte a tarifa antiga do tenant (tabela de tarifação + conjunto de
parâmetros em vigor) em rascunhos de `pricing.reference_premiums` e
`pricing.factors`. Nada é publicado: os rascunhos seguem o ciclo normal
(simular, submeter, aprovar por outra pessoa). Ver
`apps.business_config.application.legacy_tariff_migration`."""
from __future__ import annotations

import datetime
import json

from django.core.management.base import BaseCommand, CommandError

from apps.business_config.application import legacy_tariff_migration
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.models import Tenant

ACTOR = "migrate_legacy_tariffs"


class Command(BaseCommand):
    help = "Converte a tarifa antiga em rascunhos da configuração de negócio (não publica nada)."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-code", required=True)
        parser.add_argument("--dry-run", action="store_true", help="Só mostra o que seria criado.")
        parser.add_argument("--effective-from", default=None, help="Vigência dos rascunhos (AAAA-MM-DD); por omissão hoje.")

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(code=options["tenant_code"]).first()
        if tenant is None:
            raise CommandError(f"Não existe nenhum tenant com o código '{options['tenant_code']}'.")
        start = datetime.date.fromisoformat(options["effective_from"]) if options["effective_from"] else None
        token = CurrentActorProvider.bind(
            Actor(actor_id=ACTOR, tenant_id=TenantId.parse(tenant.id), roles=frozenset({Role.ADMIN}), scopes=frozenset())
        )
        try:
            report = legacy_tariff_migration.migrate(dry_run=options["dry_run"], effective_from=start)
        finally:
            CurrentActorProvider.reset(token)
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, default=str))
