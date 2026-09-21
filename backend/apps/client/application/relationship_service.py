"""Catálogo real de relações familiares (ROADMAP_ANGOLA_CUSTOMIZATION.md
OD-003 / OPEN_DECISIONS.md#S03-RELATIONSHIP-001, decisão do Product Owner
2026-09-21).

Mirrors apps/product/application/benefit_service.py's pattern exactly:
`RelationshipCode` is `TenantScopedModel` (no cross-tenant catalog table
exists in this schema), so the fixed catalogue is seeded per-tenant,
idempotently, the first time it is needed.

The 5 values are the Product Owner's own list (cônjuge/equiparado,
descendentes directos, ascendentes directos — pais e avós) plus the two
already in use by every test/demo tenant (TITULAR, OUTRO) — nothing here
invents a value the Product Owner did not name.
"""
from __future__ import annotations

import uuid
from typing import Any

from apps.foundation.application.context import CurrentTenantProvider
from apps.client.domain.enums import RelationshipCategory
from apps.client.domain.errors import UnknownRelationshipCodeError
from apps.client.infrastructure.models import RelationshipCode

MARKET_CATALOG: list[dict[str, str]] = [
    {"code": "TITULAR", "label": "Titular", "category": RelationshipCategory.TITULAR.value},
    {"code": "CONJUGE", "label": "Cônjuge ou Equiparado(a)", "category": RelationshipCategory.SPOUSE.value},
    {"code": "FILHO", "label": "Filho(a)", "category": RelationshipCategory.CHILD.value},
    {
        "code": "ASCENDENTE",
        "label": "Pai / Mãe / Avô / Avó (Ascendente Directo)",
        "category": RelationshipCategory.ASCENDANT.value,
    },
    {"code": "OUTRO", "label": "Outro", "category": RelationshipCategory.OTHER.value},
]


def ensure_relationship_catalog(tenant_id: uuid.UUID) -> None:
    """Idempotent: creates the 5 fixed relationship codes for a tenant if
    any are missing. Never touches a row that already exists (a tenant may
    have edited the label; this must not clobber that)."""
    for entry in MARKET_CATALOG:
        RelationshipCode.objects.get_or_create(
            tenant_id=tenant_id,
            code=entry["code"],
            defaults={"label": entry["label"], "category": entry["category"]},
        )


def list_relationship_codes() -> Any:
    tenant_id = CurrentTenantProvider.require().value
    ensure_relationship_catalog(tenant_id)
    return RelationshipCode.objects.order_by("category", "code")


def validate_relationship_code(*, tenant_id: uuid.UUID, code: str) -> RelationshipCode:
    """Raises UnknownRelationshipCodeError (400 VALIDATION-400) when `code`
    is not one of this tenant's catalogue values — the enforcement point
    apps/client/application/member_service.py calls before persisting a
    Member, replacing the previous "any non-empty string is accepted"
    behaviour."""
    ensure_relationship_catalog(tenant_id)
    relationship_code = RelationshipCode.objects.filter(code=code).first()
    if relationship_code is None:
        raise UnknownRelationshipCodeError(
            f"'{code}' is not a valid relationshipCode for this tenant "
            f"(see GET /api/v1/relationship-codes for the allowed values)"
        )
    return relationship_code
