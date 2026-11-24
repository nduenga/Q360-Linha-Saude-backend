"""Conta do cliente na app: idioma e apagar conta (a Apple exige que se possa
apagar a conta dentro da app — roadmap_mobile.md, Fase 4)."""
from __future__ import annotations

import uuid

from django.contrib.auth.hashers import check_password
from django.db import transaction
from django.utils import timezone

from apps.customer_portal.application import device_session_service
from apps.customer_portal.domain.errors import InvalidPortalCredentialsError
from apps.customer_portal.infrastructure.models import (
    CustomerAccount,
    CustomerAccountProposer,
    CustomerDeviceSession,
    CustomerLoginChallenge,
    CustomerPushDevice,
    PortalNotification,
    PortalUsageEvent,
)
from apps.foundation.application.audit_service import AuditService
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter

LANGUAGES = ("pt", "en")
_audit = AuditService(DjangoAuditRepositoryAdapter())


def get_language(account_id: uuid.UUID) -> str:
    return CustomerAccount.objects.filter(id=account_id).values_list("language", flat=True).first() or "pt"


def set_language(account_id: uuid.UUID, language: str) -> str:
    if language not in LANGUAGES:
        raise ValueError(f"Idioma desconhecido: {language}")
    CustomerAccount.objects.filter(id=account_id).update(language=language)
    return language


def delete_account(account_id: uuid.UUID, *, password: str, correlation_id: str | None) -> None:
    """Apaga o acesso do cliente a esta seguradora. Exige a palavra-passe.

    Saem todos os dados do acesso (sessões, dispositivos, notificações, ligações
    aos proponentes, eventos de uso). A conta fica anonimizada em vez de apagada
    porque pedidos e mensagens já tratados pela seguradora a referenciam; o
    email fica livre para uma nova conta. As apólices e cotações são da
    seguradora e não se tocam."""
    account = CustomerAccount.objects.filter(id=account_id).first()
    if account is None or not account.password_hash or not check_password(password, account.password_hash):
        raise InvalidPortalCredentialsError("Palavra-passe incorreta")
    with transaction.atomic():
        CustomerPushDevice.objects.filter(customer_account_id=account.id).delete()
        CustomerDeviceSession.objects.filter(customer_account_id=account.id).delete()
        PortalNotification.objects.filter(customer_account_id=account.id).delete()
        CustomerLoginChallenge.objects.filter(customer_account_id=account.id).delete()
        CustomerAccountProposer.objects.filter(customer_account_id=account.id).delete()
        PortalUsageEvent.objects.filter(customer_account_id=account.id).delete()
        CustomerAccount.objects.filter(id=account.id).update(
            email=f"apagado-{account.id}@apagado.invalid", password_hash=None, password_set_at=None,
            email_verified=False, push_preferences={}, deleted_at=timezone.now(),
        )
    _audit.record(
        action="customer_portal.account_deleted", entity_type="CustomerAccount", entity_id=str(account.id),
        correlation_id=correlation_id,
    )
