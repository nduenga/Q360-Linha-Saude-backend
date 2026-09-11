"""DRF permission classes for Q360's two independent authorization layers:

- `require_permission`: business RBAC from DOC-001 s18 (Q360-S1-04).
- `require_scope`: HTTP-contract-level OAuth2 scopes from ART-006's
  `security` block on each operation. Both are enforced; neither
  substitutes for the other (see domain/scopes.py).

Usage: `permission_classes = [require_permission(Permission.QUOTE_CREATE)]`
or `permission_classes = [require_scope(Scope.READ)]`.
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.foundation.application.permission_evaluator import PermissionEvaluator
from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope


def require_permission(permission: Permission) -> type[BasePermission]:
    class _RequiresPermission(BasePermission):
        def has_permission(self, request, view) -> bool:
            actor = getattr(getattr(request, "user", None), "actor", None)
            return PermissionEvaluator.is_authorised(actor, permission)

    _RequiresPermission.__name__ = f"Requires_{permission.name}"
    return _RequiresPermission


def require_scope(scope: Scope) -> type[BasePermission]:
    class _RequiresScope(BasePermission):
        def has_permission(self, request, view) -> bool:
            actor = getattr(getattr(request, "user", None), "actor", None)
            return actor is not None and actor.has_scope(scope)

    _RequiresScope.__name__ = f"RequiresScope_{scope.name}"
    return _RequiresScope
