"""Authenticated actor value object.

An Actor represents *who* is performing an action, resolved from validated
JWT claims by the JwtActorAdapter (DOC-004 s6.1). It never carries the raw
token, and it is the only source CurrentActorProvider/CurrentTenantProvider
may be bound from (Q360-S1-04: tenant must come from a non-falsifiable
context, never from client-supplied headers or body fields).
"""
from __future__ import annotations

import dataclasses

from apps.foundation.domain.permissions import Permission, Role, effective_role_permissions
from apps.foundation.domain.scopes import Scope
from apps.foundation.domain.tenant import TenantId


@dataclasses.dataclass(frozen=True, slots=True)
class Actor:
    actor_id: str
    tenant_id: TenantId
    roles: frozenset[Role]
    scopes: frozenset[Scope] = frozenset()
    actor_type: str = "USER"
    # ROADMAP_PORTAL_CLIENTE.md Fase 0 — the second, narrower security
    # boundary a `actor_type="CUSTOMER"` actor needs on top of tenant
    # scoping: opaque Proposer id strings (never a business-module type
    # here, to keep foundation free of a dependency on apps.client per
    # DOC-004 s3.1) this actor is allowed to see. Always empty for
    # USER/SYSTEM/SERVICE actors — see
    # apps.customer_portal.infrastructure.scoping.require_customer_proposer_ids
    # for the fail-closed accessor customer_portal code must use instead of
    # reading this field directly.
    customer_proposer_ids: frozenset[str] = frozenset()

    @property
    def permissions(self) -> frozenset[Permission]:
        granted: set[Permission] = set()
        by_role = effective_role_permissions(self.tenant_id.value if self.actor_type != "CUSTOMER" else None)
        for role in self.roles:
            granted |= by_role.get(role, frozenset())
        return frozenset(granted)

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions

    def has_scope(self, scope: Scope) -> bool:
        return scope in self.scopes
