"""Account-management endpoints are gated by role alone (ADMIN), the same
way the frontend's own /administracao route already is (router.tsx's
AdminRoute) - not `require_permission`/`require_scope`
(apps.foundation.interfaces.permissions), which gate DOC-001 s18's business
matrix; managing staff accounts predates that matrix (it used to be an
external Auth0 dashboard concern) and DOC-001 has no permission for it.
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.foundation.domain.permissions import Role


class IsAdminRole(BasePermission):
    def has_permission(self, request, view) -> bool:
        actor = getattr(getattr(request, "user", None), "actor", None)
        return actor is not None and Role.ADMIN in actor.roles
