"""Biblioteca de coberturas gerida pelo GTE (requisito R6).

CRUD, desativar/reativar, histórico versionado (`benefit_revision`),
rollback, utilização por planos e importação/exportação XLSX/CSV.

Regras (PDF "Coberturas e Capitais"):
  - só se criam coberturas `COMPLEMENTARY` (as `BASE` são as do PDF e estão
    em todos os planos);
  - uma cobertura `BASE` não se desativa;
  - desativar/reverter exige justificação (`reason`, ≥10 caracteres) e fica
    em auditoria com `before`/`after`;
  - desativar uma cobertura não a retira dos planos que já a usam (mesma
    garantia que `Plan.INACTIVE`: nada em curso quebra) — só deixa de ser
    oferecida para novos planos.
"""
from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Max

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.change_audit import change_metadata, require_reason
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.product.application.benefit_service import ensure_market_catalog
from apps.product.domain.enums import BenefitStatus
from apps.product.domain.errors import (
    BenefitRevisionNotFoundError,
    DuplicateCodeError,
    InvalidBenefitDefinitionError,
    ProtectedBenefitError,
    RowVersionMismatchError,
)
from apps.product.domain.market_catalog import BASE, COMPLEMENTARY, GUARANTEE_FORMS
from apps.product.infrastructure.models import Benefit, BenefitRevision, PlanBenefit

_audit = AuditService(DjangoAuditRepositoryAdapter())

_CODE_PATTERN_STRICT = re.compile(r"^[A-Z][A-Z0-9_]{1,59}$")
# Pattern mais permissivo que o utilizador final pode escrever no formulário
# (minúsculas, hífen, ponto, espaço). Antes de validar/gravar normalizamos para
# a forma canónica UPPER_SNAKE_CASE: só o padrão estrito é aceite no fim.
_CODE_PATTERN_LENIENT = re.compile(r"^[A-Za-z][ A-Za-z0-9._-]{1,59}$")


def _normalise_code(raw_code: str) -> str:
    """Converte códigos inseridos manualmente para a forma canónica:
    maiúsculas, espaços/pontos/hífens → '_', remove duplicados.

    Exemplos:
      'Consulta Externa' → 'CONSULTA_EXTERNA'
      'Plano-Gold.01'     → 'PLANO_GOLD_01'
      'urgencia_24h'      → 'URGENCIA_24H'
    """
    import re as _re

    if not raw_code:
        return raw_code
    upper = raw_code.strip().upper()
    # Substitui todos os separadores permitidos pelo formulário por '_'
    replaced = _re.sub(r"[ .\-]+", "_", upper)
    # Remove underscores duplicadas (nunca devem existir dois ou mais seguidos)
    replaced = _re.sub(r"_+", "_", replaced)
    # Tira underscore leading/trailing (por segurança)
    return replaced.strip("_")
_ALLOWED_CURRENCIES = {"AOA", "USD"}


def validate_definition(definition: Any) -> dict[str, Any]:
    """Light structural validation of `definition_json`. Unknown keys are
    kept (the GTE can add notes/fields the engine ignores); known keys must
    have the right shape."""
    if definition is None:
        return {}
    if not isinstance(definition, dict):
        raise InvalidBenefitDefinitionError("definition tem de ser um objeto JSON")
    form = definition.get("guaranteeForm")
    if form is not None and form not in GUARANTEE_FORMS:
        raise InvalidBenefitDefinitionError(
            f"definition.guaranteeForm '{form}' não é um de {sorted(GUARANTEE_FORMS)}"
        )
    for key in ("typicalSublimits", "exclusions"):
        value = definition.get(key)
        if value is not None and not isinstance(value, list):
            raise InvalidBenefitDefinitionError(f"definition.{key} tem de ser uma lista")
    if definition.get("requiresPriorApproval") is not None and not isinstance(
        definition["requiresPriorApproval"], bool
    ):
        raise InvalidBenefitDefinitionError("definition.requiresPriorApproval tem de ser verdadeiro ou falso")
    currencies = definition.get("allowedCurrencies")
    if currencies is not None:
        if not isinstance(currencies, list) or not currencies or not set(currencies) <= _ALLOWED_CURRENCIES:
            raise InvalidBenefitDefinitionError(
                f"definition.allowedCurrencies tem de ser uma lista não vazia dentro de {sorted(_ALLOWED_CURRENCIES)}"
            )
    waiting = definition.get("typicalWaitingDays")
    if waiting is not None:
        if not isinstance(waiting, dict):
            raise InvalidBenefitDefinitionError("definition.typicalWaitingDays tem de ser um objeto")
        for segment, rng in waiting.items():
            if (
                not isinstance(rng, list)
                or len(rng) != 2
                or not all(isinstance(n, int) and n >= 0 for n in rng)
                or rng[0] > rng[1]
            ):
                raise InvalidBenefitDefinitionError(
                    f"definition.typicalWaitingDays.{segment} tem de ser [mín, máx] com 0 <= mín <= máx"
                )
    return definition


def benefit_snapshot(benefit: Benefit) -> dict[str, Any]:
    return {
        "code": benefit.code,
        "name": benefit.name,
        "category": benefit.benefit_type,
        "description": benefit.description,
        "status": benefit.status,
        "definition": benefit.definition_json,
    }


def _record_revision(*, benefit: Benefit, action: str, reason: str | None) -> BenefitRevision:
    tenant_id = CurrentTenantProvider.require().value
    actor = CurrentActorProvider.get()
    last = BenefitRevision.objects.filter(benefit=benefit).aggregate(m=Max("revision_no"))["m"] or 0
    return BenefitRevision.objects.create(
        tenant_id=tenant_id,
        benefit=benefit,
        revision_no=last + 1,
        action=action,
        snapshot_json=benefit_snapshot(benefit),
        reason=reason,
        changed_by=actor.actor_id if actor else "unknown",
    )


def create_benefit(
    *, code: str, name: str, description: str | None, definition: dict[str, Any] | None
) -> Benefit:
    # Normalização amigável: o utilizador pode escrever "Plano Doutor Dantas"
    # e nós gravamos automaticamente como "PLANO_DOUTOR_DANTAS". Só levantamos
    # erro se o resultado final não obedecer ao padrão estrito do sistema.
    if not _CODE_PATTERN_LENIENT.match(code):
        raise InvalidBenefitDefinitionError(
            "O código tem de começar por uma letra e ter 2 a 60 caracteres alfanuméricos, espaços, hífenes, sublinhados ou pontos"
        )
    code = _normalise_code(code)
    if not _CODE_PATTERN_STRICT.match(code):
        raise InvalidBenefitDefinitionError(
            f"O código normalizado '{code}' não cumpre o padrão ^[A-Z][A-Z0-9_]{{1,59}}$: retire números iniciais ou caracteres especiais e tente de novo"
        )
    definition = validate_definition(definition)
    tenant_id = CurrentTenantProvider.require().value
    ensure_market_catalog(tenant_id)
    try:
        with transaction.atomic():
            benefit = Benefit.objects.create(
                tenant_id=tenant_id,
                code=code,
                name=name,
                benefit_type=COMPLEMENTARY,
                description=description,
                definition_json=definition,
            )
            _record_revision(benefit=benefit, action="CREATED", reason=None)
    except IntegrityError as exc:
        raise DuplicateCodeError(f"O código de cobertura '{code}' já existe neste tenant") from exc
    _audit.record(
        action="benefit.created",
        entity_type="Benefit",
        entity_id=str(benefit.id),
        metadata=change_metadata(after=benefit_snapshot(benefit)),
    )
    return benefit


def update_benefit(
    *,
    benefit: Benefit,
    name: str,
    description: str | None,
    definition: dict[str, Any] | None,
    row_version: int,
    reason: str | None = None,
) -> Benefit:
    definition = validate_definition(definition)
    before = benefit_snapshot(benefit)
    with transaction.atomic():
        updated = Benefit.objects.filter(id=benefit.id, row_version=row_version).update(
            name=name, description=description, definition_json=definition, row_version=row_version + 1
        )
        if updated == 0:
            raise RowVersionMismatchError(
                f"A versão da cobertura {benefit.id} ({row_version}) não coincide com a versão atual; recarregue e tente de novo"
            )
        benefit.refresh_from_db()
        _record_revision(benefit=benefit, action="UPDATED", reason=reason)
    _audit.record(
        action="benefit.updated",
        entity_type="Benefit",
        entity_id=str(benefit.id),
        metadata=change_metadata(before=before, after=benefit_snapshot(benefit), reason=reason),
    )
    return benefit


def set_benefit_status(*, benefit: Benefit, active: bool, reason: str | None) -> Benefit:
    reason = require_reason(reason)
    if not active and benefit.benefit_type == BASE:
        raise ProtectedBenefitError(
            f"A cobertura '{benefit.code}' é obrigatória (BASE) e não pode ser desativada"
        )
    target = BenefitStatus.ACTIVE.value if active else BenefitStatus.INACTIVE.value
    before = benefit_snapshot(benefit)
    if benefit.status != target:
        with transaction.atomic():
            Benefit.objects.filter(id=benefit.id).update(status=target, row_version=benefit.row_version + 1)
            benefit.refresh_from_db()
            _record_revision(benefit=benefit, action="REACTIVATED" if active else "DEACTIVATED", reason=reason)
        _audit.record(
            action="benefit.reactivated" if active else "benefit.deactivated",
            entity_type="Benefit",
            entity_id=str(benefit.id),
            metadata=change_metadata(
                before=before,
                after=benefit_snapshot(benefit),
                reason=reason,
                impact={"plansUsingBenefit": PlanBenefit.objects.filter(benefit=benefit).count()},
            ),
        )
    return benefit


def list_revisions(*, benefit: Benefit):
    return BenefitRevision.objects.filter(benefit=benefit).order_by("-revision_no")


def get_revision(*, benefit: Benefit, revision_no: int) -> BenefitRevision:
    revision = BenefitRevision.objects.filter(benefit=benefit, revision_no=revision_no).first()
    if revision is None:
        raise BenefitRevisionNotFoundError(f"A cobertura {benefit.id} não tem a revisão {revision_no}")
    return revision


def rollback_benefit(*, benefit: Benefit, revision_no: int, reason: str | None) -> Benefit:
    """Restores name/description/definition/status of `revision_no` as a NEW
    revision (history is never rewritten). `category` is never restored: a
    BASE coverage cannot become COMPLEMENTARY by rolling back."""
    reason = require_reason(reason)
    revision = get_revision(benefit=benefit, revision_no=revision_no)
    snapshot = revision.snapshot_json
    target_status = snapshot.get("status", benefit.status)
    if target_status == BenefitStatus.INACTIVE.value and benefit.benefit_type == BASE:
        raise ProtectedBenefitError(f"A cobertura '{benefit.code}' é BASE e não pode ser restaurada para INACTIVE")
    before = benefit_snapshot(benefit)
    with transaction.atomic():
        Benefit.objects.filter(id=benefit.id).update(
            name=snapshot["name"],
            description=snapshot.get("description"),
            definition_json=snapshot.get("definition") or {},
            status=target_status,
            row_version=benefit.row_version + 1,
        )
        benefit.refresh_from_db()
        _record_revision(benefit=benefit, action=f"ROLLBACK_TO_{revision_no}", reason=reason)
    _audit.record(
        action="benefit.rolled_back",
        entity_type="Benefit",
        entity_id=str(benefit.id),
        metadata=change_metadata(
            before=before, after=benefit_snapshot(benefit), reason=reason, restoredRevision=revision_no
        ),
    )
    return benefit


def benefit_usage(*, benefit: Benefit) -> list[dict[str, Any]]:
    rows = (
        PlanBenefit.objects.filter(benefit=benefit)
        .select_related("plan", "plan__product")
        .order_by("plan__product__code", "plan__code")
    )
    return [
        {
            "planId": str(r.plan_id),
            "planCode": r.plan.code,
            "planName": r.plan.name,
            "planStatus": r.plan.status,
            "productId": str(r.plan.product_id),
            "productCode": r.plan.product.code,
            "inclusion": (r.configuration_json or {}).get("inclusion", "INCLUDED"),
        }
        for r in rows
    ]


# --------------------------------------------------------- import / export
EXPORT_COLUMNS = ["code", "name", "category", "description", "status", "definition_json"]


def export_rows(*, benefits) -> list[list[str]]:
    rows = [list(EXPORT_COLUMNS)]
    for b in benefits:
        rows.append(
            [
                b.code,
                b.name,
                b.benefit_type or "",
                b.description or "",
                b.status,
                json.dumps(b.definition_json or {}, ensure_ascii=False),
            ]
        )
    return rows


def export_csv(*, benefits) -> bytes:
    buffer = io.StringIO()
    csv.writer(buffer).writerows(export_rows(benefits=benefits))
    return buffer.getvalue().encode("utf-8-sig")


def export_xlsx(*, benefits) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "coberturas"
    for row in export_rows(benefits=benefits):
        sheet.append(row)
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


def _parse_rows(*, filename: str, content: bytes) -> list[dict[str, str]]:
    name = filename.lower()
    if name.endswith(".xlsx"):
        from openpyxl import load_workbook

        sheet = load_workbook(io.BytesIO(content), read_only=True, data_only=True).active
        iterator = sheet.iter_rows(values_only=True)
        aliases = {
            "código": "code", "codigo": "code", "nome": "name", "descrição": "description",
            "descricao": "description", "definição (json)": "definition_json",
            "definicao (json)": "definition_json", "categoria": "category",
        }
        header = [aliases.get(str(h or "").strip().casefold(), str(h or "").strip().lower()) for h in next(iterator, [])]
        return [
            {header[i]: ("" if v is None else str(v)).strip() for i, v in enumerate(row) if i < len(header)}
            for row in iterator
            if any(v not in (None, "") for v in row)
        ]
    raise InvalidBenefitDefinitionError("Formato não suportado. Carregue o modelo Excel .xlsx.")


def import_benefits(*, filename: str, content: bytes, dry_run: bool) -> dict[str, Any]:
    """Row-by-row upsert by `code`. A bad row never aborts the others: it is
    reported (`errors`) and skipped. `category`/`status` columns are
    ignored for existing rows (BASE protection; deactivation needs a
    reason) and a row may not create a BASE coverage."""
    rows = _parse_rows(filename=filename, content=content)
    tenant_id = CurrentTenantProvider.require().value
    ensure_market_catalog(tenant_id)
    created: list[str] = []
    updated: list[str] = []
    errors: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):  # row 1 is the header
        code = (row.get("code") or "").strip().upper()
        name = (row.get("name") or "").strip()
        try:
            if not code or not name:
                raise InvalidBenefitDefinitionError("código e nome são obrigatórios")
            if not _CODE_PATTERN_LENIENT.match(code):
                raise InvalidBenefitDefinitionError(
                    "O código tem de começar por uma letra e ter 2 a 60 caracteres alfanuméricos/espaços/hífenes/sublinhados/pontos"
                )
            code = _normalise_code(code)
            if not _CODE_PATTERN_STRICT.match(code):
                raise InvalidBenefitDefinitionError(f"O código normalizado '{code}' tem de cumprir ^[A-Z][A-Z0-9_]{{1,59}}$")
            definition_raw = row.get("definition_json") or ""
            try:
                definition = json.loads(definition_raw) if definition_raw else None
            except json.JSONDecodeError as exc:
                raise InvalidBenefitDefinitionError(f"definition_json não é JSON válido: {exc.msg}") from exc
            validate_definition(definition)
            description = row.get("description") or None
            existing = Benefit.objects.filter(code=code).first()
            if existing is None:
                category = (row.get("category") or "COMPLEMENTAR").upper()
                category = {"COMPLEMENTAR": COMPLEMENTARY, "BASE": BASE}.get(category, category)
                if category == BASE:
                    raise InvalidBenefitDefinitionError("Uma cobertura BASE não pode ser criada por importação")
                if not dry_run:
                    create_benefit(code=code, name=name, description=description, definition=definition)
                created.append(code)
            else:
                if not dry_run:
                    update_benefit(
                        benefit=existing,
                        name=name,
                        description=description,
                        definition=definition if definition is not None else existing.definition_json,
                        row_version=existing.row_version,
                        reason="import",
                    )
                updated.append(code)
        except (InvalidBenefitDefinitionError, DuplicateCodeError) as exc:
            errors.append({"row": index, "code": code or None, "message": str(exc)})
    return {"dryRun": dry_run, "created": created, "updated": updated, "errors": errors}
