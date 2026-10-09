"""Login por email + palavra-passe do Portal Cliente.

Primeiro acesso: o cliente indica a referência (apólice ou cotação) e o
documento; o código vai para o email **já guardado no proponente** — nunca
para um email escrito por quem pede. Quem controla essa caixa de correio e
conhece referência + documento define a palavra-passe. «Esqueci-me» usa o
mesmo código, pedido só com o email.

Reaproveita o que já existe: o código é um `CustomerLoginChallenge` (de
`purpose="SET_PASSWORD"`), o bloqueio é o de `domain.lockout`, o token é o de
`PortalTokenService`. Pressupõe, como `CustomerPortalAuthService`, que a vista
já ligou um actor `CUSTOMER` ao inquilino do URL.
"""
from __future__ import annotations

import datetime
import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.client.infrastructure.models import Proposer
from apps.customer_portal.domain.errors import (
    InvalidPortalCredentialsError,
    PortalAccountLockedError,
    PortalNoEmailOnFileError,
    PortalPolicyNotFoundError,
    PortalRegistrationMismatchError,
)
from apps.customer_portal.domain.lockout import LockoutState, is_locked, register_failure, register_success
from apps.customer_portal.domain.password import mask_email, validate_password_strength
from apps.customer_portal.infrastructure.email_sender import send_set_password_email
from apps.customer_portal.infrastructure.models import (
    CustomerAccount,
    CustomerAccountProposer,
    CustomerLoginChallenge,
)
from apps.customer_portal.infrastructure.otp import generate_otp, hash_otp
from apps.customer_portal.infrastructure.otp import verify_otp as _matches_otp_hash
from apps.customer_portal.infrastructure.portal_token import PortalTokenService
from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.policy.infrastructure.models import Policy
from apps.quote.domain.enums import QuoteStatus
from apps.quote.infrastructure.models import Quote

_audit = AuditService(DjangoAuditRepositoryAdapter())
_tokens = PortalTokenService()
_PURPOSE = "SET_PASSWORD"
# Hash fixo para gastar o mesmo tempo quando a conta não existe (não revelar emails).
_DUMMY_HASH = make_password("q360-portal-dummy-password")


def _normalise(email: str) -> str:
    return email.strip().lower()


def _tenant_id() -> uuid.UUID:
    return CurrentTenantProvider.require().value


def _resolve_proposer(*, reference: str, registration_number: str) -> Proposer:
    """A policy number or a (non-draft) quote number, plus the holder's document."""
    reference = reference.strip()
    proposer_id = (
        Policy.objects.filter(policy_number=reference).values_list("proposer_id", flat=True).first()
        or Quote.objects.filter(quote_number=reference)
        .exclude(status=QuoteStatus.DRAFT.value)
        .values_list("proposer_id", flat=True)
        .first()
    )
    proposer = Proposer.objects.filter(id=proposer_id).first() if proposer_id else None
    if proposer is None:
        raise PortalPolicyNotFoundError(f"Não foi encontrada nenhuma apólice ou cotação com a referência '{reference}'")
    if proposer.registration_number != registration_number.strip():
        raise PortalRegistrationMismatchError("O número de registo (registrationNumber) não corresponde ao titular desta apólice ou cotação")
    return proposer


def _account_for(email: str) -> CustomerAccount | None:
    return CustomerAccount.objects.filter(email__iexact=email).first()


def _assert_not_locked(account: CustomerAccount) -> None:
    state = LockoutState(failed_attempts=account.failed_otp_attempts, locked_until=account.locked_until)
    if is_locked(state, now=timezone.now()):
        raise PortalAccountLockedError("Conta temporariamente bloqueada após tentativas falhadas repetidas")


def _register_failure(account: CustomerAccount, *, audit_action: str, correlation_id: str | None) -> bool:
    """Counts one failed attempt; returns True if it locked the account."""
    state = register_failure(
        LockoutState(failed_attempts=account.failed_otp_attempts, locked_until=account.locked_until),
        now=timezone.now(),
        max_attempts=settings.CUSTOMER_PORTAL_MAX_FAILED_ATTEMPTS,
        lockout_minutes=settings.CUSTOMER_PORTAL_LOCKOUT_MINUTES,
    )
    CustomerAccount.objects.filter(id=account.id).update(
        failed_otp_attempts=state.failed_attempts, locked_until=state.locked_until
    )
    _audit.record(
        action=audit_action, entity_type="CustomerAccount", entity_id=str(account.id),
        correlation_id=correlation_id, metadata={"locked": state.locked_until is not None},
    )
    return state.locked_until is not None


def _issue_code(account: CustomerAccount) -> str:
    otp = generate_otp()
    CustomerLoginChallenge.objects.create(
        tenant_id=_tenant_id(), customer_account=account, otp_hash=hash_otp(otp), purpose=_PURPOSE,
        expires_at=timezone.now() + datetime.timedelta(seconds=settings.CUSTOMER_PORTAL_OTP_TTL_SECONDS),
    )
    return otp


def _consume_code(account: CustomerAccount, otp: str, *, correlation_id: str | None) -> CustomerLoginChallenge:
    _assert_not_locked(account)
    challenge = (
        CustomerLoginChallenge.objects.filter(
            customer_account=account, purpose=_PURPOSE, consumed_at__isnull=True, expires_at__gte=timezone.now()
        )
        .order_by("-created_at")
        .first()
    )
    if challenge is None or not _matches_otp_hash(otp, challenge.otp_hash):
        if _register_failure(account, audit_action="customer_portal.set_password_code_failed", correlation_id=correlation_id):
            raise PortalAccountLockedError("Conta bloqueada após tentativas falhadas repetidas")
        raise InvalidPortalCredentialsError("Código inválido ou expirado")
    return challenge


def _finish(account: CustomerAccount, challenge: CustomerLoginChallenge, password: str, *, audit_action: str,
            correlation_id: str | None) -> tuple[str, int]:
    now = timezone.now()
    with transaction.atomic():
        CustomerLoginChallenge.objects.filter(id=challenge.id).update(consumed_at=now)
        CustomerAccount.objects.filter(id=account.id).update(
            password_hash=make_password(password), password_set_at=now, email_verified=True,
            failed_otp_attempts=0, locked_until=None,
        )
    _audit.record(action=audit_action, entity_type="CustomerAccount", entity_id=str(account.id), correlation_id=correlation_id)
    return _issue_token(account)


def _issue_token(account: CustomerAccount) -> tuple[str, int]:
    proposer_ids = list(
        CustomerAccountProposer.objects.filter(customer_account=account).values_list("proposer_id", flat=True)
    )
    return _tokens.issue(tenant_id=_tenant_id(), customer_account_id=account.id, proposer_ids=proposer_ids)


class CustomerPortalPasswordAuthService:
    # ------------------------------------------------------ primeiro acesso
    def first_access_request(self, *, reference: str, registration_number: str, correlation_id: str | None) -> str:
        """Sends the code to the proposer's email on file; returns it masked."""
        proposer = _resolve_proposer(reference=reference, registration_number=registration_number)
        email = _normalise(proposer.email or "")
        if "@" not in email:
            raise PortalNoEmailOnFileError("Não há nenhum email registado para este cliente; contacte o seu mediador Q360")
        with transaction.atomic():
            account = _account_for(email) or CustomerAccount.objects.create(tenant_id=_tenant_id(), email=email)
            _assert_not_locked(account)
            CustomerAccountProposer.objects.get_or_create(
                tenant_id=_tenant_id(), customer_account=account, proposer=proposer
            )
            otp = _issue_code(account)
        send_set_password_email(to_email=account.email, otp=otp)
        _audit.record(
            action="customer_portal.first_access_requested", entity_type="CustomerAccount",
            entity_id=str(account.id), correlation_id=correlation_id,
        )
        return mask_email(account.email)

    def first_access_confirm(
        self, *, reference: str, registration_number: str, otp: str, password: str, correlation_id: str | None
    ) -> tuple[str, int]:
        proposer = _resolve_proposer(reference=reference, registration_number=registration_number)
        email = _normalise(proposer.email or "")
        account = _account_for(email) if "@" in email else None
        if account is None:
            raise InvalidPortalCredentialsError("Não foi feito nenhum pedido de acesso para este cliente: peça primeiro um novo código")
        validate_password_strength(password, email=account.email)
        challenge = _consume_code(account, otp, correlation_id=correlation_id)
        return _finish(account, challenge, password, audit_action="customer_portal.password_set", correlation_id=correlation_id)

    # ----------------------------------------------------- esqueci-me
    def password_reset_request(self, *, email: str, correlation_id: str | None) -> None:
        """Never says whether the email has an account."""
        account = _account_for(_normalise(email))
        if account is None:
            return
        try:
            _assert_not_locked(account)
        except PortalAccountLockedError:
            return
        otp = _issue_code(account)
        send_set_password_email(to_email=account.email, otp=otp)
        _audit.record(
            action="customer_portal.password_reset_requested", entity_type="CustomerAccount",
            entity_id=str(account.id), correlation_id=correlation_id,
        )

    def password_reset_confirm(
        self, *, email: str, otp: str, password: str, correlation_id: str | None
    ) -> tuple[str, int]:
        account = _account_for(_normalise(email))
        if account is None:
            raise InvalidPortalCredentialsError("Código inválido ou expirado")
        validate_password_strength(password, email=account.email)
        challenge = _consume_code(account, otp, correlation_id=correlation_id)
        return _finish(account, challenge, password, audit_action="customer_portal.password_reset", correlation_id=correlation_id)

    # --------------------------------------------------------- entrar
    def login(self, *, email: str, password: str, correlation_id: str | None) -> tuple[str, int]:
        account = _account_for(_normalise(email))
        if account is None or not account.password_hash:
            check_password(password, _DUMMY_HASH)  # same cost as a real check
            raise InvalidPortalCredentialsError("Email ou palavra-passe inválidos")
        _assert_not_locked(account)
        if not check_password(password, account.password_hash):
            if _register_failure(account, audit_action="customer_portal.login_failed", correlation_id=correlation_id):
                raise PortalAccountLockedError("Conta bloqueada após tentativas falhadas repetidas")
            raise InvalidPortalCredentialsError("Email ou palavra-passe inválidos")
        CustomerAccount.objects.filter(id=account.id).update(
            failed_otp_attempts=register_success().failed_attempts, locked_until=None
        )
        _audit.record(
            action="customer_portal.login_succeeded", entity_type="CustomerAccount", entity_id=str(account.id),
            correlation_id=correlation_id, metadata={"method": "password"},
        )
        return _issue_token(account)
