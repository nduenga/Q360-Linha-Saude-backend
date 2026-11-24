"""Descobrir a seguradora a partir do email (roadmap_mobile.md, Fase 1 — ponto 1).

Hoje a seguradora vem fixa na compilação da web. Na app móvel, única para
todas, o cliente escreve o email e a app descobre a(s) seguradora(s) onde ele
tem conta.

Privacidade (decisão a confirmar com o produto — ver o roadmap, «Riscos»): a
resposta só traz seguradoras quando há **exatamente uma**; sem conta ou com
várias, a resposta é a mesma lista vazia e, no caso de várias, as seguradoras
seguem por email para a caixa do próprio cliente. Assim a resposta não lista
seguradoras de quem não é dono do email quando há várias, e um email
desconhecido é igual a um email com várias contas. Continua a revelar que um
email tem conta numa só seguradora: o limite de pedidos por IP e por email é
o controlo compensatório, e a alternativa é uma lista pública de seguradoras.
"""
from __future__ import annotations

import logging

from apps.customer_portal.application.branding_service import branding_of, insurer_link, portal_enabled
from apps.customer_portal.infrastructure.email_sender import send_insurer_choice_email
from apps.customer_portal.infrastructure.models import CustomerAccount
from apps.foundation.infrastructure.models import Tenant

logger = logging.getLogger(__name__)


def discover(email: str) -> list[dict]:
    email = email.strip().lower()
    tenant_ids = list(
        CustomerAccount.all_tenants.filter(email__iexact=email).values_list("tenant_id", flat=True).distinct()
    )
    tenants = [t for t in Tenant.objects.filter(id__in=tenant_ids).order_by("name") if portal_enabled(t)]
    if len(tenants) == 1:
        return [branding_of(tenants[0])]
    if len(tenants) > 1:
        links = [(t.name, insurer_link(t.id, email=email)) for t in tenants]
        try:
            send_insurer_choice_email(to_email=email, insurers=links)
        except Exception:  # noqa: BLE001 - a resposta não pode depender do servidor de email
            logger.exception("Falha ao enviar o email de escolha de seguradora")
    return []
