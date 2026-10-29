"""Importação do modelo atuarial a partir de um Excel enviado pela interface.

O ficheiro é convertido no valor de `pricing.actuarial_model`, validado e
gravado como uma nova versão DRAFT, que segue o ciclo normal (submeter ->
aprovar por outro utilizador -> PUBLISHED). Nada é publicado diretamente e o
ficheiro original fica anexado à versão (com o SHA-256) para auditoria.

Com `product_id`, o modelo importado é a versão desse produto
(`pricing.actuarial_model@<produto>`), que substitui a geral nesse produto.
"""
from __future__ import annotations

import copy
import hashlib
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import transaction

from apps.business_config.application.resolver import BusinessConfigurationResolver
from apps.business_config.application.service import actor_id, create_configuration, tid
from apps.business_config.domain.actuarial_model import CONFIG_KEY, validate_actuarial_model
from apps.business_config.domain.errors import InvalidConfiguration
from apps.business_config.domain.scope import product_key
from apps.business_config.infrastructure.models import BusinessConfiguration, BusinessConfigurationDocument
from apps.business_config.seed.actuarial_model import ActuarialWorkbookError, build_actuarial_model

MAX_WORKBOOK_BYTES = 10 * 1024 * 1024
# Partes que não vêm do Excel e que o utilizador pode ter ajustado na
# interface: por omissão passam da versão publicada para a importada.
KEPT_FROM_PUBLISHED = ("calculation_settings", "plan_code_mapping", "coverage_code_mapping")


def summarize(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceFile": model.get("source_file"),
        "referenceDate": model.get("reference_date"),
        "modelStatus": model.get("model_status"),
        "plans": sorted(model.get("plan_code_mapping") or {}),
        "purePremiumRows": len(model.get("reference_pure_premiums") or []),
        "coverageAssumptions": len(model.get("coverage_assumptions") or []),
        "ageGenderRelativities": len(model.get("age_gender_relativities") or []),
        "regions": [r.get("region") for r in (model.get("adjustment_assumptions") or {}).get("regional_factors") or []],
        "industries": [r.get("industry") for r in model.get("industry_factors") or []],
        "loadings": (model.get("assumptions") or {}).get("loadings"),
        "paymentInstallments": (model.get("assumptions") or {}).get("payment_installments"),
    }


def build_from_upload(*, content: bytes, filename: str, effective_from: date, keep_published_settings: bool,
                      product_id=None) -> tuple[dict, list[str]]:
    if not content:
        raise InvalidConfiguration("O ficheiro está vazio.")
    if len(content) > MAX_WORKBOOK_BYTES:
        raise InvalidConfiguration(f"O ficheiro excede {MAX_WORKBOOK_BYTES // (1024 * 1024)} MB.")
    if not filename.lower().endswith(".xlsx"):
        raise InvalidConfiguration("Envie um ficheiro Excel .xlsx com a estrutura do modelo atuarial.")
    try:
        model = build_actuarial_model(content, source_name=Path(filename).name[:255])
    except ActuarialWorkbookError as exc:
        raise InvalidConfiguration(str(exc)) from exc
    except (TypeError, ValueError, KeyError, IndexError, AttributeError) as exc:
        raise InvalidConfiguration("O ficheiro não segue a estrutura do modelo atuarial (células/tabelas em falta).") from exc
    kept: list[str] = []
    if keep_published_settings:
        # O que vale hoje no produto (a versão dele ou a geral).
        published = BusinessConfigurationResolver.get(CONFIG_KEY, effective_date=effective_from, product_id=product_id)
        if published is not None and isinstance(published.value_json, dict):
            for key in KEPT_FROM_PUBLISHED:
                if key in published.value_json:
                    model[key] = copy.deepcopy(published.value_json[key])
                    kept.append(key)
    validate_actuarial_model(model)
    return model, kept


@transaction.atomic
def import_actuarial_workbook(request, *, content: bytes, filename: str, effective_from: date,
                              keep_published_settings: bool = True, product_id=None) -> tuple[BusinessConfiguration, list[str]]:
    model, kept = build_from_upload(content=content, filename=filename, effective_from=effective_from,
                                    keep_published_settings=keep_published_settings, product_id=product_id)
    sha256 = hashlib.sha256(content).hexdigest()
    key = product_key(CONFIG_KEY, product_id) if product_id else CONFIG_KEY
    configuration = create_configuration(
        request, key, model, effective_from,
        metadata={"source": "EXCEL_IMPORT", "fileName": model["source_file"], "sha256": sha256,
                  "keptFromPublished": kept},
    )
    _attach_workbook(configuration, content=content, filename=model["source_file"], sha256=sha256)
    return configuration, kept


def _attach_workbook(configuration: BusinessConfiguration, *, content: bytes, filename: str, sha256: str) -> None:
    tenant = str(tid())
    document_id = uuid.uuid4()
    relative = Path("business-config") / tenant / str(configuration.id) / str(document_id)
    path = Path(settings.MEDIA_ROOT) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    BusinessConfigurationDocument.all_tenants.create(
        id=document_id, tenant_id=tenant, configuration_id=configuration.id, document_type="ACTUARIAL_WORKBOOK",
        original_filename=filename,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        storage_key=str(relative), checksum=sha256, metadata_json={}, uploaded_by=actor_id(),
    )
