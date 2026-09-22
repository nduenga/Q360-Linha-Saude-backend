"""CustomerPortalAuthService (ROADMAP_PORTAL_CLIENTE.md Fase 0).

Orchestrates the two-step login: `request_access` resolves
quoteNumber+registrationNumber+email to a (CustomerAccount, Proposer) pair
— creating the pair the first time it's seen — and emails an OTP;
`verify_otp` checks the OTP against the lockout policy (OD-PORTAL-003) and,
on success, issues a signed customer-portal session token.

Both methods assume `CurrentActorProvider` is already bound, by the view,
to a `actor_type="CUSTOMER"` Actor scoped to the tenant resolved from the
request URL — so every Proposer/Quote/CustomerAccount query below is
automatically tenant-scoped by `TenantScopedManager`, exactly like every
other module in this project (apps.customer_portal.interfaces.views).
"""
from __future__ import annotations

import datetime

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.client.infrastructure.models import Proposer
from apps.customer_portal.domain.errors import InvalidPortalCredentialsError, PortalAccountLockedError
from apps.customer_portal.domain.lockout import LockoutState, is_locked, register_failure, register_success
from apps.customer_portal.infrastructure.email_sender import send_otp_email
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
from apps.quote.infrastructure.models import Quote

_audit = AuditService(DjangoAuditRepositoryAdapter())
_tokens = PortalTokenService()


class CustomerPortalAuthService:
    def request_access(
        self, *, quote_number: str, registration_number: str, email: str, correlation_id: str | None
    ) -> None:
        """Always completes without raising — the response must not reveal
        whether quoteNumber/registrationNumber matched anything (avoids
        confirming a real policy/document number to an unauthenticated
        caller)."""
        proposer = self._resolve_proposer(quote_number=quote_number, registration_number=registration_number)
        if proposer is None:
            return

        tenant_id = CurrentTenantProvider.require().value
        with transaction.atomic():
            account, _ = CustomerAccount.objects.get_or_create(tenant_id=tenant_id, email=email, defaults={})
            CustomerAccountProposer.objects.get_or_create(
                tenant_id=tenant_id, customer_account=account, proposer=proposer
            )
            if is_locked(
                LockoutState(failed_attempts=account.failed_otp_attempts, locked_until=account.locked_until),
                now=timezone.now(),
            ):
                # Never send a fresh OTP to a locked account, but still say
                # nothing different to the caller than the happy path.
                return

            otp = generate_otp()
            CustomerLoginChallenge.objects.create(
                tenant_id=tenant_id,
                customer_account=account,
                otp_hash=hash_otp(otp),
                expires_at=timezone.now() + datetime.timedelta(seconds=settings.CUSTOMER_PORTAL_OTP_TTL_SECONDS),
            )

        send_otp_email(to_email=email, otp=otp)
        _audit.record(
            action="customer_portal.access_requested",
            entity_type="CustomerAccount",
            entity_id=str(account.id),
            correlation_id=correlation_id,
        )

    def verify_otp(
        self, *, quote_number: str, registration_number: str, email: str, otp: str, correlation_id: str | None
    ) -> tuple[str, int]:
        tenant_id = CurrentTenantProvider.require().value
        proposer = self._resolve_proposer(quote_number=quote_number, registration_number=registration_number)
        account = None
        if proposer is not None:
            account = CustomerAccount.objects.filter(tenant_id=tenant_id, email=email).first()
        if account is None:
            raise InvalidPortalCredentialsError("Credentials do not match any active account")

        now = timezone.now()
        state = LockoutState(failed_attempts=account.failed_otp_attempts, locked_until=account.locked_until)
        if is_locked(state, now=now):
            raise PortalAccountLockedError("Account temporarily locked after repeated failed attempts")

        challenge = (
            CustomerLoginChallenge.objects.filter(
                tenant_id=tenant_id, customer_account=account, consumed_at__isnull=True, expires_at__gte=now
            )
            .order_by("-created_at")
            .first()
        )
        if challenge is None or not _matches_otp_hash(otp, challenge.otp_hash):
            new_state = register_failure(
                state,
                now=now,
                max_attempts=settings.CUSTOMER_PORTAL_MAX_FAILED_ATTEMPTS,
                lockout_minutes=settings.CUSTOMER_PORTAL_LOCKOUT_MINUTES,
            )
            CustomerAccount.objects.filter(id=account.id).update(
                failed_otp_attempts=new_state.failed_attempts, locked_until=new_state.locked_until
            )
            _audit.record(
                action="customer_portal.otp_failed",
                entity_type="CustomerAccount",
                entity_id=str(account.id),
                correlation_id=correlation_id,
                metadata={"locked": new_state.locked_until is not None},
            )
            if new_state.locked_until is not None:
                raise PortalAccountLockedError("Account locked after repeated failed attempts")
            raise InvalidPortalCredentialsError("Invalid or expired code")

        proposer_ids = list(
            CustomerAccountProposer.objects.filter(tenant_id=tenant_id, customer_account=account).values_list(
                "proposer_id", flat=True
            )
        )
        success_state = register_success()
        with transaction.atomic():
            CustomerLoginChallenge.objects.filter(id=challenge.id).update(consumed_at=now)
            CustomerAccount.objects.filter(id=account.id).update(
                failed_otp_attempts=success_state.failed_attempts,
                locked_until=success_state.locked_until,
                email_verified=True,
            )

        token, ttl_seconds = _tokens.issue(
            tenant_id=tenant_id, customer_account_id=account.id, proposer_ids=proposer_ids
        )
        _audit.record(
            action="customer_portal.login_succeeded",
            entity_type="CustomerAccount",
            entity_id=str(account.id),
            correlation_id=correlation_id,
        )
        return token, ttl_seconds

    @staticmethod
    def _resolve_proposer(*, quote_number: str, registration_number: str) -> Proposer | None:
        quote = (
            Quote.objects.filter(quote_number=quote_number, status="APPROVED")
            .select_related("proposer")
            .first()
        )
        if quote is None or quote.proposer is None:
            return None
        if quote.proposer.registration_number != registration_number:
            return None
        return quote.proposer
