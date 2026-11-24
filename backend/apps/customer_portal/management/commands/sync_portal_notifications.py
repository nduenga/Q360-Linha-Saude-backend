"""Gera (e envia por push) as notificações calculadas a partir do estado:
prestação em atraso, cotação aprovada, proposta de renovação, endosso para
aceitar, apólice a vencer.

Na web essas notificações só aparecem quando o cliente abre a central; com a
app móvel o push tem de chegar sem ele abrir nada, por isso este comando corre
de hora a hora (cron / agendador do servidor):

    python manage.py sync_portal_notifications

Só trata contas com pelo menos um dispositivo com push ativo, de tenants ativos
com o Portal do Cliente ligado. Idempotente: cada notificação tem chave única,
logo corrê-lo duas vezes não repete pushes.
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from apps.customer_portal.application import notifications_service
from apps.customer_portal.infrastructure.models import CustomerAccount, CustomerAccountProposer, CustomerPushDevice
from apps.foundation.application import tenant_status
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId
from apps.platform_admin.application.tenant_settings import module_enabled

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sincroniza as notificações do portal (e envia os pushes novos) das contas com a app instalada."

    def handle(self, *args, **options):
        pairs = set(
            CustomerPushDevice.all_tenants.filter(active=True).values_list("tenant_id", "customer_account_id")
        )
        done = failed = 0
        for tenant_id, account_id in sorted(pairs, key=str):
            if tenant_status.is_blocked(tenant_id) or not module_enabled(tenant_id, "customerPortal"):
                continue
            proposer_ids = [
                str(p)
                for p in CustomerAccountProposer.all_tenants.filter(
                    tenant_id=tenant_id, customer_account_id=account_id
                ).values_list("proposer_id", flat=True)
            ]
            if not CustomerAccount.all_tenants.filter(tenant_id=tenant_id, id=account_id).exists():
                continue
            token = CurrentActorProvider.bind(
                Actor(
                    actor_id=str(account_id), tenant_id=TenantId.parse(str(tenant_id)), roles=frozenset(),
                    scopes=frozenset(), actor_type="CUSTOMER", customer_proposer_ids=frozenset(proposer_ids),
                )
            )
            try:
                notifications_service.sync_account(account_id)
                done += 1
            except Exception:  # noqa: BLE001 - uma conta com problemas não pára as outras
                failed += 1
                logger.exception("Falha ao sincronizar as notificações da conta %s", account_id)
            finally:
                CurrentActorProvider.reset(token)
        self.stdout.write(f"Contas sincronizadas: {done}; com falha: {failed}.")
