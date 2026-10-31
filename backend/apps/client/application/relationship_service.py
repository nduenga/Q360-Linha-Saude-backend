
"""Catálogo de relações familiares por tenant.

TITULAR é usado pelo proponente individual. Em organizações, COLABORADOR é o
papel do empregado e o titular do seu agregado; ambos são opções contextuais,
não relações familiares do dropdown normal.
"""
from __future__ import annotations

import uuid

from apps.foundation.application.context import CurrentTenantProvider
from apps.client.domain.enums import RelationshipCategory
from apps.client.domain.errors import UnknownRelationshipCodeError
from apps.client.infrastructure.models import RelationshipCode


# Catálogo com relações internas e familiares. Os papéis do agregado são
# listados apenas nos contextos HOLDER e EMPLOYEE.
MARKET_CATALOG: list[dict[str, str]] = [
    {
        "code": "COLABORADOR",
        "label": "Colaborador(a)",
        "category": RelationshipCategory.COLLABORATOR.value,
    },
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
        "code": "PAI",
        "label": "Pai",
        "category": RelationshipCategory.ASCENDANT.value,
    },
    {
        "code": "MAE",
        "label": "Mãe",
        "category": RelationshipCategory.ASCENDANT.value,
    },
    {
        "code": "ASCENDENTE",
        "label": "Pai / Mãe / Avô / Avó (Ascendente Direto)",
        "category": RelationshipCategory.ASCENDANT.value,
    },
    {
        "code": "DESCENDENTE",
        "label": "Descendente",
        "category": RelationshipCategory.DESCENDANT.value,
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


def list_relationship_codes(*, household_role: str = "DEPENDENT"):
    """Return choices for a holder or dependant selection control.

    ``HOLDER`` returns ``TITULAR``; ``EMPLOYEE`` returns ``COLABORADOR``.
    ``DEPENDENT`` excludes both anchor roles.
    """
    tenant_id = CurrentTenantProvider.require().value
    ensure_relationship_catalog(tenant_id)

    queryset = RelationshipCode.objects.filter(tenant_id=tenant_id)
    if household_role == "HOLDER":
        return queryset.filter(category=RelationshipCategory.TITULAR.value).order_by("code")
    if household_role == "EMPLOYEE":
        return queryset.filter(category=RelationshipCategory.COLLABORATOR.value).order_by("code")
    return queryset.exclude(category__in=(RelationshipCategory.TITULAR.value, RelationshipCategory.COLLABORATOR.value)).order_by("category", "code")


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
