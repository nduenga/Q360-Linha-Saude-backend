"""ROADMAP_PORTAL_CLIENTE.md Fase 1, migrated to Policy in Fase 6
(DECISIONS_TAKEN.md#S09-POLICY-001): "sobretudo composição de serviços de
aplicação já existentes e testados" — nenhuma regra de negócio nova aqui,
só resolução scoped-ao-cliente das entidades que os serviços já
existentes (policy, product/benefit) já sabem tratar.

Toda a resolução passa por `require_customer_proposer_ids` (fail-closed)
— um `policyNumber` só é aceite se pertencer a um dos `Proposer` ligados
ao `customer_account` autenticado; nunca se confia num `proposerId`/
`planId` vindo do pedido do cliente (esses vêm sempre do `Policy` já
resolvido).
"""
from __future__ import annotations

import uuid

from django.db.models import QuerySet

from apps.customer_portal.domain.errors import PortalResourceNotFoundError
from apps.customer_portal.infrastructure.scoping import require_customer_proposer_ids
from apps.policy.infrastructure.models import Policy


def _scoped_proposer_ids() -> list[uuid.UUID]:
    return [uuid.UUID(pid) for pid in require_customer_proposer_ids()]


def list_my_policies() -> QuerySet[Policy]:
    proposer_ids = _scoped_proposer_ids()
    if not proposer_ids:
        return Policy.objects.none()
    return Policy.objects.filter(proposer_id__in=proposer_ids).order_by("-created_at")


def resolve_my_policy(policy_number: str) -> Policy:
    proposer_ids = _scoped_proposer_ids()
    policy = (
        Policy.objects.filter(policy_number=policy_number, proposer_id__in=proposer_ids).first()
        if proposer_ids
        else None
    )
    if policy is None:
        raise PortalResourceNotFoundError("No policy found for this policyNumber")
    return policy
