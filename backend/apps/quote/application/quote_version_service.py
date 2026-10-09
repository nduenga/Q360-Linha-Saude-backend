"""Versões da cotação (R1): guardar, versionar, recuperar.

Uma versão é um ponto de gravação **imutável** do estado editável da
cotação: data de início, escolhas (opcionais, opção A–E, "e se..."), ajustes
ACTIVE, população (com o estado de elegibilidade) e decisões de
preexistência, mais o prémio resultante. Cria-se:

  - automaticamente (`PRICED`) quando o estado ao recalcular é diferente da
    última versão (mesmo estado = nada a gravar);
  - a pedido (`MANUAL`, com motivo);
  - ao restaurar (`RESTORED`), ao copiar (`CLONE`) e ao renovar (`RENEWAL`).

Restaurar nunca reescreve o histórico: aplica o estado de uma versão à
cotação (população incluída) como **uma nova versão**, com motivo e
auditoria. Os ajustes ativos que são substituídos ficam `REMOVED`.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.change_audit import change_metadata, require_reason
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.pricing.application.plan_dimensions import resolve_plan_pricing_context
from apps.pricing.domain.money import round_amount
from apps.quote.application import quote_service, simulator_service
from apps.quote.domain.enums import QuoteStatus
from apps.quote.domain.errors import QuoteStateError, ReferencedEntityNotFoundError
from apps.quote.infrastructure.models import Quote, QuoteAdjustment, QuoteMember, QuoteVersion

_audit = AuditService(DjangoAuditRepositoryAdapter())
_EDITABLE = (QuoteStatus.DRAFT.value, QuoteStatus.READY.value)


class QuoteVersionNotFoundError(DomainProblem):
    http_status = 404
    problem_code = "NOT-FOUND"


def capture_state(quote: Quote) -> dict[str, Any]:
    members = []

    for qm in quote.members.select_related("member").order_by("created_at", "id"):
        member = qm.member

        member_name = " ".join(
            filter(
                None,
                [
                    member.first_name,
                    member.last_name,
                ],
            )
        ).strip()

        members.append(
            {
                "memberId": str(qm.member_id),
                "memberName": member_name,
                "status": qm.status,
                "preExisting": qm.pre_existing_json or {},
            }
        )
    adjustments = [
        {k: v for k, v in item.items() if k != "id"} for item in quote_service.active_adjustments_for_context(quote)
    ]
    pricing = None
    run = quote.latest_pricing_run if quote.latest_pricing_run_id else None
    if run is not None and run.status == "CALCULATED":
        pricing = {
            "pricingRunId": str(run.id),
            "totalAmount": str(round_amount(run.total_amount)),
            "currencyCode": run.currency_code,
        }
    return {
        "quoteType": quote.quote_type,
        "sourcePolicyId": str(quote.source_policy_id) if quote.source_policy_id else None,
        "planId": str(quote.plan_id),
        "effectiveDate": quote.effective_date.isoformat(),
        "selection": quote.selection_json or {},
        "adjustments": adjustments,
        "members": members,
        "pricing": pricing,
    }


def _checksum(state: dict[str, Any]) -> str:
    payload = {**state, "pricing": {k: v for k, v in (state.get("pricing") or {}).items() if k != "pricingRunId"}}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def record_version(*, quote: Quote, source: str, reason: str | None = None, dedupe: bool = True) -> QuoteVersion | None:
    state = capture_state(quote)
    checksum = _checksum(state)
    latest = QuoteVersion.objects.filter(quote=quote).order_by("-version_no").first()
    if dedupe and latest is not None and latest.checksum == checksum:
        return None
    actor = CurrentActorProvider.get()
    pricing = state.get("pricing")
    return QuoteVersion.objects.create(
        tenant_id=quote.tenant_id,
        quote=quote,
        version_no=(latest.version_no if latest else 0) + 1,
        source=source,
        reason=reason,
        snapshot_json=state,
        checksum=checksum,
        total_amount=Decimal(pricing["totalAmount"]) if pricing else None,
        currency_code=pricing["currencyCode"] if pricing else None,
        created_by=actor.actor_id if actor else "unknown",
    )


def save_version(*, quote: Quote, reason: str | None) -> QuoteVersion:
    """Manual save point. Always creates a version (no dedupe): the user
    asked for it explicitly and the reason is part of the record."""
    reason = require_reason(reason)
    version = record_version(quote=quote, source="MANUAL", reason=reason, dedupe=False)
    _audit.record(
        action="quote.version_saved",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata=change_metadata(after={"versionNo": version.version_no}, reason=reason),
    )
    return version


def list_versions(*, quote: Quote):
    return QuoteVersion.objects.filter(quote=quote).order_by("-version_no")


def get_version(*, quote: Quote, version_no: int) -> QuoteVersion:
    version = QuoteVersion.objects.filter(quote=quote, version_no=version_no).first()
    if version is None:
        raise QuoteVersionNotFoundError(f"A cotação {quote.id} não tem a versão {version_no}")
    return version


# ------------------------------------------------------------------- diff
def _adjustment_key(adj: dict[str, Any]) -> str:
    return f"{adj['kind']}:{adj['value']}:{adj['scope']}:{adj.get('memberId')}"


def diff_states(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    def add(field: str, was: Any, now: Any) -> None:
        if was != now:
            changes.append({"field": field, "before": was, "after": now})

    add("effectiveDate", before["effectiveDate"], after["effectiveDate"])
    add("planId", before["planId"], after["planId"])
    for key in sorted(set(before["selection"]) | set(after["selection"])):
        add(f"selection.{key}", before["selection"].get(key), after["selection"].get(key))
    before_adj = {_adjustment_key(a): a for a in before["adjustments"]}
    after_adj = {_adjustment_key(a): a for a in after["adjustments"]}
    for key in sorted(set(after_adj) - set(before_adj)):
        changes.append({"field": "adjustments", "before": None, "after": after_adj[key]})
    for key in sorted(set(before_adj) - set(after_adj)):
        changes.append({"field": "adjustments", "before": before_adj[key], "after": None})
    def _key(member: dict[str, Any]) -> str:
        # Versions saved between 2026-10-07 and this fix have no memberId.
        return member.get("memberId") or member.get("memberName") or ""

    def _label(member: dict[str, Any]) -> str:
        return member.get("memberName") or member.get("memberId") or ""

    before_members = {_key(m): m for m in before.get("members", [])}
    after_members = {_key(m): m for m in after.get("members", [])}

    for key in sorted(set(after_members) - set(before_members)):
        changes.append({"field": "members", "before": None, "after": _label(after_members[key])})
    for key in sorted(set(before_members) - set(after_members)):
        changes.append({"field": "members", "before": _label(before_members[key]), "after": None})
    for key in sorted(set(before_members) & set(after_members)):
        add(
            f"members.{_label(after_members[key]) or key}.preExisting",
            before_members[key].get("preExisting"),
            after_members[key].get("preExisting"),
        )
    before_total = (before.get("pricing") or {}).get("totalAmount")
    after_total = (after.get("pricing") or {}).get("totalAmount")
    add("pricing.totalAmount", before_total, after_total)
    return changes


def compare_versions(*, quote: Quote, version_no: int, against: int | None) -> dict[str, Any]:
    base = get_version(quote=quote, version_no=version_no)
    if against is None:
        other_state, label = capture_state(quote), "current"
    else:
        other_state, label = get_version(quote=quote, version_no=against).snapshot_json, str(against)
    return {
        "versionNo": version_no,
        "against": label,
        "changes": diff_states(base.snapshot_json, other_state),
    }


# ---------------------------------------------------------------- restore
def restore_version(*, quote: Quote, version_no: int, reason: str | None) -> tuple[Quote, dict[str, Any]]:
    if quote.status not in _EDITABLE:
        raise QuoteStateError(f"A cotação {quote.id} está em {quote.status}; só se pode restaurar uma versão em rascunho (DRAFT) ou pronta (READY)")
    reason = require_reason(reason)
    version = get_version(quote=quote, version_no=version_no)
    state = version.snapshot_json
    if state["planId"] != str(quote.plan_id):
        raise ReferencedEntityNotFoundError("A versão pertence a outro plano e não pode ser restaurada")

    # Validate before touching anything: the plan/coverage configuration may
    # have changed since the version was saved.
    resolve_plan_pricing_context(plan=quote.plan, selection=state["selection"], effective_date=quote.effective_date)
    for spec in state["adjustments"]:
        simulator_service._enforce_authority(quote, {"kind": spec["kind"], "value": Decimal(spec["value"])})

    actor = CurrentActorProvider.get()
    before = capture_state(quote)
    report: dict[str, list[str]] = {"addedMembers": [], "removedMembers": [], "skippedMembers": []}
    import datetime

    with transaction.atomic():
        wanted = {m["memberId"]: m for m in state["members"] if m.get("memberId")}
        current = {str(qm.member_id): qm for qm in quote.members.all()}
        if len(wanted) != len(state["members"]):
            # Version saved without member ids: the population cannot be restored, keep it as is.
            wanted = {member_id: {"preExisting": qm.pre_existing_json or {}} for member_id, qm in current.items()}
            report["skippedMembers"].append("A versão não guarda os ids das pessoas seguras: a população não foi alterada.")
        for member_id in sorted(set(current) - set(wanted)):
            quote_service.remove_quote_member(quote=quote, member_id=uuid.UUID(member_id))
            report["removedMembers"].append(member_id)
        for member_id in sorted(set(wanted) - set(current)):
            try:
                quote_service.add_quote_member(quote=quote, member_id=uuid.UUID(member_id), correlation_id=None)
                report["addedMembers"].append(member_id)
            except DomainProblem as exc:
                report["skippedMembers"].append(f"{member_id}: {exc}")
        quote.refresh_from_db()

        Quote.objects.filter(id=quote.id).update(
            effective_date=datetime.date.fromisoformat(state["effectiveDate"]),
            valid_until=quote_service._default_valid_until(datetime.date.fromisoformat(state["effectiveDate"])),
            selection_json=state["selection"],
            row_version=quote.row_version + 1,
        )
        quote.refresh_from_db()

        QuoteAdjustment.objects.filter(quote=quote, status="ACTIVE").update(
            status="REMOVED",
            removed_by=actor.actor_id if actor else "unknown",
            removed_at=timezone.now(),
            removed_reason=f"Restauro da versão {version_no}: {reason}",
        )
        for spec in state["adjustments"]:
            QuoteAdjustment.objects.create(
                tenant_id=quote.tenant_id,
                quote=quote,
                kind=spec["kind"],
                value=Decimal(spec["value"]),
                scope=spec["scope"],
                member_id=spec.get("memberId"),
                reason=spec.get("reason") or f"Restauro da versão {version_no}: {reason}",
                applied_by=actor.actor_id if actor else "unknown",
            )
        for member_id, saved in wanted.items():
            QuoteMember.objects.filter(quote=quote, member_id=member_id).update(pre_existing_json=saved["preExisting"])
        quote_service._demote_to_draft_if_ready(quote)
        quote.refresh_from_db()
        quote = simulator_service._reprice(quote)
        restored = record_version(quote=quote, source="RESTORED", reason=f"Restaurada a versão {version_no}: {reason}", dedupe=False)

    _audit.record(
        action="quote.version_restored",
        entity_type="Quote",
        entity_id=str(quote.id),
        metadata=change_metadata(
            before={"state": before},
            after={"restoredVersion": version_no, "newVersion": restored.version_no},
            reason=reason,
            impact={
                "previousTotal": (before.get("pricing") or {}).get("totalAmount"),
                "newTotal": str(round_amount(quote.latest_pricing_run.total_amount)) if quote.latest_pricing_run_id else None,
            },
        ),
    )
    return quote, {**report, "newVersionNo": restored.version_no}
