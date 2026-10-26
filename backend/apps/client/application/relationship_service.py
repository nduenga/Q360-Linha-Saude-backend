
"""Catálogo de relações familiares por tenant.

O código TITULAR é mantido no catálogo interno para permitir a criação
do primeiro membro e validar as regras de parentesco, mas não é
disponibilizado como opção no endpoint público GET /api/v1/relationship-codes.
"""
from __future__ import annotations

import uuid

from apps.foundation.application.context import CurrentTenantProvider
from apps.client.domain.enums import RelationshipCategory
from apps.client.domain.errors import UnknownRelationshipCodeError
from apps.client.infrastructure.models import RelationshipCode


# Catálogo interno: TITULAR é necessário para as regras de negócio,
# mas deve ser ocultado na listagem pública.
MARKET_CATALOG: list[dict[str, str]] = [
    {
        "code": "TITULAR",
        "label": "Titular",
        "category": RelationshipCategory.TITULAR.value,
    },
    {
        "code": "CONJUGE",
        "label": "Cônjuge ou Equiparado(a)",
        "category": RelationshipCategory.SPOUSE.value,
    },
    {
        "code": "FILHO",
        "label": "Filho(a)",
        "category": RelationshipCategory.CHILD.value,
    },
    {
        "code": "ASCENDENTE",
        "label": "Pai / Mãe / Avô / Avó (Ascendente Direto)",
        "category": RelationshipCategory.ASCENDANT.value,
    },
    {
        "code": "OUTRO",
        "label": "Outro",
        "category": RelationshipCategory.OTHER.value,
    },
]


def ensure_relationship_catalog(tenant_id: uuid.UUID) -> None:
    """Cria idempotentemente os códigos internos de parentesco do tenant.

    Os registos existentes não são alterados, para preservar eventuais
    alterações de etiquetas feitas pelo tenant.
    """
    for entry in MARKET_CATALOG:
        RelationshipCode.objects.get_or_create(
            tenant_id=tenant_id,
            code=entry["code"],
            defaults={
                "label": entry["label"],
                "category": entry["category"],
            },
        )


def list_relationship_codes():
    """Devolve apenas as relações que podem ser escolhidas na interface."""
    tenant_id = CurrentTenantProvider.require().value
    ensure_relationship_catalog(tenant_id)

    return (
        RelationshipCode.objects
        .filter(tenant_id=tenant_id)
        .exclude(code="TITULAR")
        .order_by("category", "code")
    )


def validate_relationship_code(
    *,
    tenant_id: uuid.UUID,
    code: str,
) -> RelationshipCode:
    """Valida um código no catálogo do tenant, incluindo TITULAR."""
    ensure_relationship_catalog(tenant_id)

    relationship_code = RelationshipCode.objects.filter(
        tenant_id=tenant_id,
        code=code,
    ).first()

    if relationship_code is None:
        raise UnknownRelationshipCodeError(
            f"'{code}' não é um código de parentesco válido neste tenant "
            "(consulte GET /api/v1/relationship-codes para ver os valores "
            "permitidos para seleção)"
        )

    return relationship_code
