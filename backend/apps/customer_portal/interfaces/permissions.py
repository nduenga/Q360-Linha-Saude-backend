"""ROADMAP_PORTAL_CLIENTE.md Fase 0: "APENAS o módulo de portal deve
decidir o que um actor CUSTOMER pode fazer, fora da matriz DOC-001" — this
permission class is deliberately not `require_scope`
(apps.foundation.interfaces.permissions), which gates DOC-001/ART-006
staff scopes that a CUSTOMER actor never has.
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission


class IsCustomerPortalActor(BasePermission):
    def has_permission(self, request, view) -> bool:
        actor = getattr(getattr(request, "user", None), "actor", None)
        return actor is not None and actor.actor_type == "CUSTOMER"
