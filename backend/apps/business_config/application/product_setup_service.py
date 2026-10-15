"""Configuração de tarifação de um produto (grupos de opções, campos, valores e
fórmulas) — ver `domain/product_setup.py`.

É uma configuração de negócio com a chave `product.pricing_setup:<produto>`:
o rascunho grava-se aqui; submeter, aprovar (outra pessoa), rejeitar,
comparar e reverter usam as rotas gerais `/business-config/configurations`.
"""
from __future__ import annotations

import datetime
from typing import Any

from django.db.models import Q
from django.utils import timezone

from apps.business_config.application import service
from apps.business_config.domain.errors import ConfigurationStateError
from apps.business_config.domain.product_setup import ProductSetup, config_key, parse_product_setup
from apps.business_config.infrastructure.models import BusinessConfiguration
from apps.foundation.application.context import CurrentTenantProvider

OPEN_STATUSES = ("DRAFT", "REJECTED")


def _rows(product_id):
    return BusinessConfiguration.objects.filter(
        tenant_id=CurrentTenantProvider.require().value, config_key=config_key(product_id)
    )


def published(product_id, day: datetime.date | None = None) -> BusinessConfiguration | None:
    day = day or timezone.localdate()
    return (
        _rows(product_id).filter(status="PUBLISHED", effective_from__lte=day)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=day))
        .order_by("-version_no").first()
    )


def open_draft(product_id) -> BusinessConfiguration | None:
    return _rows(product_id).filter(status__in=OPEN_STATUSES).order_by("-version_no").first()


def pending(product_id) -> BusinessConfiguration | None:
    return _rows(product_id).filter(status="PENDING_APPROVAL").order_by("-version_no").first()


def load_for_pricing(product_id, day: datetime.date) -> tuple[BusinessConfiguration, ProductSetup] | None:
    """A configuração publicada em vigor no dia do cálculo, já interpretada."""
    row = published(product_id, day)
    if row is None:
        return None
    return row, parse_product_setup(row.value_json)


def describe(row: BusinessConfiguration | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": str(row.id), "versionNo": row.version_no, "status": row.status,
        "effectiveFrom": row.effective_from, "effectiveTo": row.effective_to, "rowVersion": row.row_version,
        "checksum": row.checksum, "createdBy": row.created_by, "approvedBy": row.approved_by,
        "createdAt": row.created_at, "publishedAt": row.published_at, "value": row.value_json,
    }


def state(product) -> dict[str, Any]:
    current = published(product.id)
    draft = open_draft(product.id)
    waiting = pending(product.id)
    working = draft or waiting or current
    tokens: list[dict[str, Any]] = []
    form = None
    if working is not None:
        setup = parse_product_setup(working.value_json)
        tokens = setup.tokens()
    if current is not None:
        form = parse_product_setup(current.value_json).form()
    return {
        "productId": str(product.id), "productCode": product.code, "configKey": config_key(product.id),
        "published": describe(current), "draft": describe(draft), "pendingApproval": describe(waiting),
        "tokens": tokens, "form": form,
    }


def save_draft(request, product, *, value: dict, effective_from: datetime.date | None, row_version: int | None):
    """Grava o rascunho do produto: edita o que está aberto (DRAFT/REJECTED)
    ou cria uma nova versão DRAFT. Uma versão à espera de aprovação bloqueia."""
    if pending(product.id) is not None:
        raise ConfigurationStateError(
            "Há uma versão à espera de aprovação: aprove-a ou rejeite-a antes de criar outra."
        )
    draft = open_draft(product.id)
    if draft is not None:
        return service.update_configuration(request, draft, value, effective_from=effective_from, row_version=row_version)
    return service.create_configuration(
        request, config_key(product.id), value, effective_from or timezone.localdate(),
        metadata={"productId": str(product.id), "productCode": product.code},
    )


def history(product) -> list[dict[str, Any]]:
    return [
        {k: v for k, v in describe(row).items() if k != "value"}
        for row in _rows(product.id).order_by("-version_no")
    ]


def working_setup(product, value: dict | None) -> ProductSetup:
    """O que testar: o valor enviado, ou o rascunho, ou a versão publicada."""
    if value is not None:
        return parse_product_setup(value)
    row = open_draft(product.id) or pending(product.id) or published(product.id)
    if row is None:
        raise ConfigurationStateError("O produto ainda não tem grupos, campos, valores ou fórmulas configurados.")
    return parse_product_setup(row.value_json)
