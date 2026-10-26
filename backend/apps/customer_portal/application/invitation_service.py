"""Convite para o Portal do Cliente quando a seguradora regista um proponente.

O primeiro acesso normal pede o número de uma apólice ou cotação, que um
cliente acabado de registar ainda não tem. Por isso o convite cria já a conta
do portal (sem palavra-passe) ligada ao proponente, e o link leva o cliente a
definir a palavra-passe com um código enviado para o mesmo email.
"""
from __future__ import annotations

import logging
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction

from apps.client.infrastructure.models import Proposer
from apps.customer_portal.infrastructure.email_sender import send_portal_invitation_email
from apps.customer_portal.infrastructure.models import CustomerAccount, CustomerAccountProposer
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.foundation.infrastructure.models import Tenant

logger = logging.getLogger(__name__)
_audit = AuditService(DjangoAuditRepositoryAdapter())


def invite_proposer(proposer: Proposer) -> str | None:
    """Liga o proponente a uma conta do portal e envia o convite depois do
    commit. Devolve o email convidado, ou None se o proponente não tem email.
    Uma falha no envio não desfaz o registo do proponente (fica no log)."""
    email = (proposer.email or "").strip().lower()
    if "@" not in email:
        return None
    tenant_id = CurrentTenantProvider.require().value
    account = CustomerAccount.objects.filter(email__iexact=email).first()
    existing = account is not None
    if not existing:
        # Conta nova: fica já ligada a este proponente (o código para definir a
        # palavra-passe vai para o email que a seguradora registou).
        account = CustomerAccount.objects.create(tenant_id=tenant_id, email=email)
        CustomerAccountProposer.objects.create(tenant_id=tenant_id, customer_account=account, proposer=proposer)
    # Conta já existente (p.ex. o email de um mediador usado em vários clientes):
    # não se liga sozinha — quem vê os dados deste cliente tem de provar a
    # referência e o documento no «Primeiro acesso», como até aqui.
    insurer = Tenant.objects.filter(id=tenant_id).values_list("name", flat=True).first() or "Seguradora"
    path = "primeiro" if existing else "recuperar"
    link = f"{settings.CUSTOMER_PORTAL_URL}/{path}?{urlencode({'email': email, 'convite': '1'})}"

    def _send() -> None:
        try:
            send_portal_invitation_email(to_email=email, client_name=proposer.display_name, insurer_name=insurer,
                                         link=link, existing_account=existing)
        except Exception:  # noqa: BLE001 - o registo do cliente não depende do servidor de email
            logger.exception("Falha ao enviar o convite do portal para o proponente %s", proposer.id)

    transaction.on_commit(_send)
    _audit.record(action="customer_portal.invitation_sent", entity_type="Proposer", entity_id=str(proposer.id),
                  metadata={"email": email, "existingAccount": existing, "linked": not existing})
    return email
