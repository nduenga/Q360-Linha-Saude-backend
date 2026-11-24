"""DRF authentication for the customer portal, backed by
`PortalTokenService` — never `JwtActorAdapter`/`JwtActorAuthentication`
(apps.foundation.interfaces.authentication), which validate the staff
OIDC token. Isolated on purpose (ROADMAP_PORTAL_CLIENTE.md Fase 0): a
staff Bearer token must never authenticate a customer-portal endpoint and
vice-versa. Only customer-portal views list this class in
`authentication_classes` — it is not in `REST_FRAMEWORK.
DEFAULT_AUTHENTICATION_CLASSES`.
"""
from __future__ import annotations

import uuid

from rest_framework import authentication, exceptions

from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId
from apps.foundation.interfaces.authentication import ActorUser
from apps.customer_portal.infrastructure.portal_token import InvalidPortalTokenError, PortalTokenService

_tokens = PortalTokenService()


class CustomerPortalJwtAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode("utf-8")
        if not header or not header.lower().startswith(f"{self.keyword.lower()} "):
            return None
        token = header[len(self.keyword) + 1 :].strip()
        if not token:
            return None

        try:
            claims = _tokens.decode(token)
        except InvalidPortalTokenError as exc:
            raise exceptions.AuthenticationFailed(str(exc)) from exc

        actor = Actor(
            actor_id=str(claims["sub"]),
            tenant_id=TenantId.parse(claims["tenant_id"]),
            roles=frozenset(),
            scopes=frozenset(),
            actor_type="CUSTOMER",
            customer_proposer_ids=frozenset(claims.get("proposer_ids") or []),
        )
        from apps.foundation.application import tenant_status

        if tenant_status.is_blocked(actor.tenant_id.value):
            raise exceptions.AuthenticationFailed("O tenant está suspenso ou inativo.")
        from apps.platform_admin.application.tenant_settings import module_enabled

        if not module_enabled(actor.tenant_id.value, "customerPortal"):
            raise exceptions.AuthenticationFailed("O Portal do Cliente não está disponível para esta seguradora.")
        session_id = claims.get("sid")
        if session_id:
            # Token de um telemóvel: vale só enquanto a sessão não for terminada
            # («Dispositivos ligados», fim de sessão, palavra-passe alterada).
            from apps.customer_portal.application import device_session_service

            try:
                active = device_session_service.is_active(uuid.UUID(session_id), uuid.UUID(claims["sub"]))
            except ValueError:
                active = False
            if not active:
                raise exceptions.AuthenticationFailed("A sessão foi terminada. Inicie sessão de novo.")
        request.portal_session_id = uuid.UUID(session_id) if session_id else None
        CurrentActorProvider.bind(actor)
        return ActorUser(actor), token

    def authenticate_header(self, request):
        return self.keyword
