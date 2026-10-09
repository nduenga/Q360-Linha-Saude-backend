"""CurrentTenantProvider / CurrentActorProvider (DOC-004 s6.1).

Backed by `contextvars` so the authenticated tenant/actor is available to
application-layer code (use cases, AuditService, TenantScopedManager)
without threading `request` through every call.

These are bound in exactly one place: `JwtActorAuthentication.authenticate`
(apps.foundation.interfaces.authentication), from a validated JWT — never
from a client-supplied header/body field (Q360-S1-04: tenant must be a
non-falsifiable security boundary, DOC-001 s20). They are reset after every
request by `ActorContextCleanupMiddleware` to prevent leakage across
requests handled by the same worker thread.
"""
from __future__ import annotations

import contextvars

from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId

_current_actor: contextvars.ContextVar[Actor | None] = contextvars.ContextVar(
    "q360_current_actor", default=None
)


class CurrentActorProvider:
    @staticmethod
    def get() -> Actor | None:
        return _current_actor.get()

    @staticmethod
    def bind(actor: Actor | None) -> contextvars.Token:
        return _current_actor.set(actor)

    @staticmethod
    def reset(token: contextvars.Token) -> None:
        _current_actor.reset(token)


class CurrentTenantProvider:
    @staticmethod
    def get() -> TenantId | None:
        actor = CurrentActorProvider.get()
        return actor.tenant_id if actor else None

    @staticmethod
    def require() -> TenantId:
        tenant_id = CurrentTenantProvider.get()
        if tenant_id is None:
            raise LookupError("Nenhum tenant autenticado no contexto atual")
        return tenant_id
