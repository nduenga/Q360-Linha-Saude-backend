"""Loads the Individual/Familiar and Grupo products and plans from the PDF
"Seguro de Saúde — Coberturas e Capitais" (indicative, editable values) into
a tenant. Same effect as `POST /api/v1/product-templates/market`, for
local/demo use without an authenticated session. Idempotent."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.models import Tenant
from apps.product.application.market_template_service import apply_market_templates


class Command(BaseCommand):
    help = "Seed the PDF 'Coberturas e Capitais' product/plan templates (indicative values) for a tenant."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-code", default="dev-tenant")

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(code=options["tenant_code"])
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Não existe nenhum tenant com o código '{options['tenant_code']}'.") from exc
        CurrentActorProvider.bind(
            Actor(actor_id="system-seed", tenant_id=TenantId.parse(tenant.id), roles=frozenset(), scopes=frozenset())
        )
        result = apply_market_templates()
        self.stdout.write(
            f"products created: {result['createdProducts']}; plans created: {result['createdPlans']}; "
            f"plans skipped (already exist): {result['skippedPlans']}"
        )
        for report in result["plans"]:
            self.stdout.write(f"  {report['planCode']}: valid={report['valid']} warnings={report['warningCount']}")
