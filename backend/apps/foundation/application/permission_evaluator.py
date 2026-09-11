"""PermissionEvaluator (DOC-004 s6.1) — RBAC/ABAC contextual.

S1 implements the RBAC half only (role -> permission, DOC-001 s18
unconditional grants). ABAC/contextual grants (the cells marked "Opc." in
DOC-001 s18) require the Authority Policy engine introduced in Sprint 7
(ART-009) and must not be approximated here.
"""
from __future__ import annotations

from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Permission


class PermissionEvaluator:
    @staticmethod
    def is_authorised(actor: Actor | None, permission: Permission) -> bool:
        if actor is None:
            return False
        return actor.has_permission(permission)
