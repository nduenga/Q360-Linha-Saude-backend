"""Authenticated actor value object.

An Actor represents *who* is performing an action, resolved from validated
JWT claims by the JwtActorAdapter (DOC-004 s6.1). It never carries the raw
token, and it is the only source CurrentActorProvider/CurrentTenantProvider
may be bound from (Q360-S1-04: tenant must come from a non-falsifiable
context, never from client-supplied headers or body fields).
"""
from __future__ import annotations

import dataclasses

from apps.foundation.domain.permissions import ROLE_PERMISSIONS, Permission, Role
from apps.foundation.domain.scopes import Scope
from apps.foundation.domain.tenant import TenantId


@dataclasses.dataclass(frozen=True, slots=True)
class Actor:
    actor_id: str
    tenant_id: TenantId
    roles: frozenset[Role]
    scopes: frozenset[Scope] = frozenset()
    actor_type: str = "USER"

    @property
    def permissions(self) -> frozenset[Permission]:
        granted: set[Permission] = set()
        for role in self.roles:
            granted |= ROLE_PERMISSIONS.get(role, frozenset())
        return frozenset(granted)

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions

    def has_scope(self, scope: Scope) -> bool:
        return scope in self.scopes
