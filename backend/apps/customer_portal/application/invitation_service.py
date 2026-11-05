"""Convite para o Portal do Cliente quando a seguradora regista um proponente individual
ou importa o titular de um proponente organizacional.

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

from apps.client.domain.errors import HouseholdValidationError
from apps.client.infrastructure.models import InsuredMember, Proposer
from apps.customer_portal.infrastructure.email_sender import send_portal_invitation_email
from apps.customer_portal.infrastructure.models import CustomerAccount, CustomerAccountProposer
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.foundation.infrastructure.models import AuditEvent, Tenant

logger = logging.getLogger(__name__)
_audit = AuditService(DjangoAuditRepositoryAdapter())
_SENT = "customer_portal.invitation_sent"
_FAILED = "customer_portal.invitation_failed"


def invite_proposer(proposer: Proposer, *, recipient_email: str | None = None) -> str | None:
    """Liga o proponente a uma conta do portal e envia o convite depois do
    commit. `recipient_email` permite convidar o titular importado de uma
    organização sem substituir o email de contacto da empresa. Devolve o
    email convidado, ou None se não houver email. Uma falha no envio não
    desfaz o registo do proponente: fica no log e na auditoria, e a ficha do
    cliente mostra-a com a opção de reenviar (`invitation_status`)."""
    raw_email = proposer.email if recipient_email is None else recipient_email
    email = (raw_email or "").strip().lower()
    if "@" not in email:
        return None
    tenant_id = CurrentTenantProvider.require().value
    account = CustomerAccount.objects.filter(email__iexact=email).first()
    # Conta já ligada a este proponente (reenvio de um convite) conta como nova:
    # o cliente continua a precisar de definir a palavra-passe, não de provar o documento.
    linked = account is not None and CustomerAccountProposer.objects.filter(
        customer_account=account, proposer=proposer
    ).exists()
    existing = account is not None and not linked
    if account is None:
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
        # A auditoria só diz «enviado» depois de o servidor de email aceitar a mensagem.
        metadata = {"email": email, "existingAccount": existing, "linked": not existing}
        try:
            send_portal_invitation_email(to_email=email, client_name=proposer.display_name, insurer_name=insurer,
                                         link=link, existing_account=existing)
        except Exception as exc:  # noqa: BLE001 - o registo do cliente não depende do servidor de email
            logger.exception("Falha ao enviar o convite do portal para o proponente %s", proposer.id)
            _audit.record(action=_FAILED, entity_type="Proposer", entity_id=str(proposer.id),
                          metadata={**metadata, "reason": type(exc).__name__})
        else:
            _audit.record(action=_SENT, entity_type="Proposer", entity_id=str(proposer.id), metadata=metadata)

    transaction.on_commit(_send)
    return email


def invitation_status(proposer: Proposer) -> dict:
    """Resultado do último convite: SENT (o servidor de email aceitou), FAILED
    (não saiu) ou NONE (ainda não houve convite). «Aceite» não prova que chegou
    à caixa de entrada: isso só o destinatário confirma."""
    event = (
        AuditEvent.objects.filter(entity_type="Proposer", entity_id=str(proposer.id), action__in=(_SENT, _FAILED))
        .order_by("-occurred_at")
        .first()
    )
    if event is None:
        return {"status": "NONE", "email": None, "occurredAt": None}
    return {
        "status": "SENT" if event.action == _SENT else "FAILED",
        "email": (event.metadata_json or {}).get("email"),
        "occurredAt": event.occurred_at,
    }


def resend_invitation(proposer: Proposer) -> dict:
    """Volta a enviar o convite para o cliente individual ou para o titular da organização."""
    recipient = None
    if proposer.proposer_type == "ORGANISATION":
        titular = InsuredMember.objects.filter(proposer=proposer, relationship_code="TITULAR", status="ACTIVE").first()
        recipient = ((titular.attributes_json or {}).get("email") or "") if titular else ""
        if not recipient:
            raise HouseholdValidationError("Indique primeiro o titular da organização, com o e-mail dele.")
    if invite_proposer(proposer, recipient_email=recipient) is None:
        raise HouseholdValidationError("Este cliente não tem um e-mail válido para receber o convite.")
    return invitation_status(proposer)
