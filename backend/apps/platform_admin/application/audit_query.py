"""Auditoria vista pela plataforma: pesquisa, exportação e alertas.

Junta duas origens:
- PLATFORM: o que os super administradores fizeram (`platform_audit_event`);
- TENANT: o trilho de cada seguradora (`audit_event`), lido sem filtro de tenant.

Cada evento traz `changes` (campo, antes, depois) quando os metadados têm
`before`/`after`, para o ecrã mostrar as alterações lado a lado."""
from __future__ import annotations

import datetime
import io
import uuid
from typing import Any

from django.db.models import Q
from django.utils import timezone

from apps.foundation.infrastructure.models import AuditEvent, Tenant
from apps.platform_admin.infrastructure.models import PlatformAdmin, PlatformAuditEvent

SOURCES = ("PLATFORM", "TENANT", "ALL")
MAX_PAGE_SIZE = 200
MAX_EXPORT_ROWS = 5000

ACTION_LABELS = {
    "platform.login_failed": "Acesso falhado de super administrador",
    "platform.login_succeeded": "Entrada de super administrador",
    "platform.tenant_created": "Seguradora criada",
    "platform.tenant_updated": "Seguradora alterada",
    "platform.tenant_status_changed": "Estado da seguradora alterado",
    "platform.tenant_settings_updated": "Identidade visual ou limites alterados",
    "platform.tenant_logo_uploaded": "Logótipo da seguradora carregado",
    "platform.tenant_viewed": "Super administrador consultou a seguradora",
    "platform.tenant_audit_viewed": "Super administrador consultou a auditoria da seguradora",
    "platform.audit_exported": "Auditoria exportada",
    "platform.tenant_admin_added": "Administrador da seguradora criado",
    "platform.tenant_account_password_reset": "Palavra-passe de utilizador reposta",
    "platform.tenant_notice_sent": "Aviso enviado aos administradores",
    "platform.tenant_notice_failed": "Falha no aviso aos administradores",
    "platform_parameter.proposed": "Parâmetro geral proposto",
    "platform_parameter.approved": "Parâmetro geral aprovado",
    "platform_parameter.rejected": "Parâmetro geral rejeitado",
    "platform_reference_table.proposed": "Tabela de referência proposta",
    "platform_reference_table.approved": "Tabela de referência aprovada",
    "platform_reference_table.rejected": "Tabela de referência rejeitada",
    "platform_template.proposed": "Modelo do fornecedor proposto",
    "platform_template.approved": "Modelo do fornecedor aprovado",
    "platform_template.rejected": "Modelo do fornecedor rejeitado",
    "staff_account.login_failed": "Acesso falhado de utilizador",
    "staff_account.created": "Utilizador criado",
    "staff_account.unlocked": "Utilizador desbloqueado",
}


def action_label(action: str) -> str:
    return ACTION_LABELS.get(action, action)


def _parse_date(value: str | None, *, end: bool = False) -> datetime.datetime | None:
    if not value:
        return None
    day = datetime.date.fromisoformat(value[:10])
    moment = datetime.datetime.combine(day, datetime.time.max if end else datetime.time.min)
    return timezone.make_aware(moment, timezone.get_current_timezone())


def _flat(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            out.update(_flat(item, f"{prefix}.{key}" if prefix else str(key)))
        return out
    return {prefix or "valor": value}


def changes_of(metadata: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Campos alterados (antes → depois) a partir de `before`/`after`."""
    metadata = metadata or {}
    if "before" not in metadata and "after" not in metadata:
        return []
    before, after = _flat(metadata.get("before")), _flat(metadata.get("after"))
    rows = []
    for field in sorted(set(before) | set(after)):
        old, new = before.get(field), after.get(field)
        if old != new:
            rows.append({"field": field, "before": old, "after": new})
    return rows


def _filters(*, tenant_id=None, actor_id=None, action=None, date_from=None, date_to=None):
    q = Q()
    if actor_id:
        q &= Q(actor_id=actor_id)
    if action:
        q &= Q(action__icontains=action)
    start, end = _parse_date(date_from), _parse_date(date_to, end=True)
    if start:
        q &= Q(occurred_at__gte=start)
    if end:
        q &= Q(occurred_at__lte=end)
    return q


def _platform_qs(*, tenant_id=None, **kwargs):
    qs = PlatformAuditEvent.objects.filter(_filters(**kwargs))
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)
    return qs


def _tenant_qs(*, tenant_id=None, **kwargs):
    qs = AuditEvent.all_tenants.filter(_filters(**kwargs))
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)
    return qs


def _names(events: list[dict[str, Any]]) -> None:
    tenant_ids, admin_ids, staff_ids = set(), set(), set()
    for e in events:
        if e["tenantId"]:
            tenant_ids.add(e["tenantId"])
        try:
            actor = uuid.UUID(str(e["actorId"]))
        except (TypeError, ValueError):
            continue
        (admin_ids if e["source"] == "PLATFORM" else staff_ids).add(actor)
    from apps.staff_accounts.infrastructure.models import StaffAccount

    tenants = {str(k): v for k, v in Tenant.objects.filter(id__in=tenant_ids).values_list("id", "name")}
    admins = {str(k): v for k, v in PlatformAdmin.objects.filter(id__in=admin_ids).values_list("id", "name")}
    staff = {str(k): v for k, v in StaffAccount.all_tenants.filter(id__in=staff_ids).values_list("id", "name")}
    for e in events:
        e["tenantName"] = tenants.get(str(e["tenantId"])) if e["tenantId"] else None
        e["actorName"] = (admins if e["source"] == "PLATFORM" else staff).get(str(e["actorId"]))


def _row(source: str, e) -> dict[str, Any]:
    return {
        "id": str(e.id), "source": source,
        "tenantId": str(e.tenant_id) if getattr(e, "tenant_id", None) else None,
        "actorId": e.actor_id, "actorType": getattr(e, "actor_type", "PLATFORM_ADMIN"),
        "action": e.action, "actionLabel": action_label(e.action),
        "entityType": e.entity_type, "entityId": e.entity_id,
        "occurredAt": e.occurred_at, "correlationId": e.correlation_id,
        "metadata": e.metadata_json or {}, "changes": changes_of(e.metadata_json),
    }


def search(*, source: str = "ALL", tenant_id=None, actor_id=None, action=None, date_from=None, date_to=None,
           page: int = 1, size: int = 50) -> dict[str, Any]:
    """Página de eventos (mais recentes primeiro) das origens pedidas."""
    if source not in SOURCES:
        source = "ALL"
    size = max(1, min(int(size or 50), MAX_PAGE_SIZE))
    page = max(1, int(page or 1))
    kwargs = dict(tenant_id=tenant_id, actor_id=actor_id, action=action, date_from=date_from, date_to=date_to)
    wanted = page * size
    rows: list[dict[str, Any]] = []
    total = 0
    if source in ("PLATFORM", "ALL"):
        qs = _platform_qs(**kwargs)
        total += qs.count()
        rows += [_row("PLATFORM", e) for e in qs.order_by("-occurred_at")[:wanted]]
    if source in ("TENANT", "ALL"):
        qs = _tenant_qs(**kwargs)
        total += qs.count()
        rows += [_row("TENANT", e) for e in qs.order_by("-occurred_at")[:wanted]]
    rows.sort(key=lambda r: r["occurredAt"], reverse=True)
    items = rows[(page - 1) * size: page * size]
    _names(items)
    return {"items": items, "page": page, "size": size, "total": total}


def export_rows(**filters) -> list[dict[str, Any]]:
    result = search(**{**filters, "page": 1, "size": MAX_PAGE_SIZE})
    rows = list(result["items"])
    page = 2
    while len(rows) < min(result["total"], MAX_EXPORT_ROWS):
        more = search(**{**filters, "page": page, "size": MAX_PAGE_SIZE})["items"]
        if not more:
            break
        rows += more
        page += 1
    return rows[:MAX_EXPORT_ROWS]


def _when(value) -> str:
    from zoneinfo import ZoneInfo

    return timezone.localtime(value, ZoneInfo("Africa/Luanda")).strftime("%d/%m/%Y %H:%M")


def _changes_text(changes: list[dict[str, Any]]) -> str:
    return "; ".join(f"{c['field']}: {c['before'] if c['before'] is not None else '—'} → "
                     f"{c['after'] if c['after'] is not None else '—'}" for c in changes)


_HEADER = ["Data", "Origem", "Seguradora", "Autor", "Ação", "Registo", "Alterações"]


def _table(rows: list[dict[str, Any]]) -> list[list[str]]:
    return [[_when(r["occurredAt"]), "Plataforma" if r["source"] == "PLATFORM" else "Seguradora",
             r.get("tenantName") or "—", r.get("actorName") or r["actorId"] or "—", r["actionLabel"],
             f"{r['entityType']} {r['entityId'] or ''}".strip(), _changes_text(r["changes"])] for r in rows]


def _filters_text(filters: dict[str, Any]) -> str:
    parts = []
    if filters.get("date_from") or filters.get("date_to"):
        parts.append(f"Período: {filters.get('date_from') or '…'} a {filters.get('date_to') or '…'}")
    if filters.get("tenant_id"):
        parts.append(f"Seguradora: {Tenant.objects.filter(id=filters['tenant_id']).values_list('name', flat=True).first() or filters['tenant_id']}")
    if filters.get("action"):
        parts.append(f"Ação contém: {filters['action']}")
    if filters.get("actor_id"):
        parts.append(f"Autor: {filters['actor_id']}")
    return " · ".join(parts) or "Sem filtros"


def export_xlsx(**filters) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    rows = export_rows(**filters)
    book = Workbook()
    sheet = book.active
    sheet.title = "Auditoria"
    sheet.append(["Auditoria Q360", _filters_text(filters)])
    sheet.append([])
    sheet.append(_HEADER)
    for cell in sheet[3]:
        cell.font = Font(bold=True)
    for row in _table(rows):
        sheet.append(row)
    for column, width in zip("ABCDEFG", (17, 12, 28, 28, 40, 30, 70)):
        sheet.column_dimensions[column].width = width
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def export_pdf(**filters) -> bytes:
    from apps.quote.application.proposal_layout import render_pdf

    rows = export_rows(**filters)
    blocks = [
        ("title", "Auditoria Q360"),
        ("kv", [("Filtros", _filters_text(filters)), ("Eventos", str(len(rows))),
                ("Gerado em", _when(timezone.now()))]),
        ("table", _HEADER, _table(rows)) if rows else ("paragraph", "Sem eventos para estes filtros."),
    ]
    return render_pdf(blocks, title="Auditoria Q360")


# --------------------------------------------------------------------- alertas
FAILED_LOGIN_THRESHOLD = 3
LEGAL_DAYS = 30


def alerts(*, now: datetime.datetime | None = None) -> list[dict[str, Any]]:
    """Acessos falhados repetidos (24 h), contas bloqueadas e alterações a
    parâmetros legais (30 dias)."""
    from apps.foundation.domain.system_parameters import DEFINITIONS
    from apps.staff_accounts.infrastructure.models import StaffAccount

    now = now or timezone.now()
    since = now - datetime.timedelta(hours=24)
    out: list[dict[str, Any]] = []

    failed: dict[tuple, int] = {}
    for tenant_id, entity_id in AuditEvent.all_tenants.filter(
        action="staff_account.login_failed", occurred_at__gte=since
    ).values_list("tenant_id", "entity_id"):
        failed[(str(tenant_id), entity_id)] = failed.get((str(tenant_id), entity_id), 0) + 1
    for entity_id in PlatformAuditEvent.objects.filter(action="platform.login_failed", occurred_at__gte=since) \
            .values_list("entity_id", flat=True):
        failed[("PLATFORM", entity_id)] = failed.get(("PLATFORM", entity_id), 0) + 1
    tenant_names = {str(k): v for k, v in Tenant.objects.values_list("id", "name")}
    staff_ids = []
    for (_, entity_id) in failed:
        try:
            staff_ids.append(uuid.UUID(str(entity_id)))
        except (TypeError, ValueError):
            pass
    names = {str(k): v for k, v in StaffAccount.all_tenants.filter(id__in=staff_ids).values_list("id", "email")}
    names.update({str(k): v for k, v in PlatformAdmin.objects.filter(id__in=staff_ids).values_list("id", "email")})
    for (scope, entity_id), count in sorted(failed.items(), key=lambda item: -item[1]):
        if count < FAILED_LOGIN_THRESHOLD:
            continue
        who = names.get(str(entity_id)) or ("email desconhecido" if not entity_id else str(entity_id))
        where = "Plataforma" if scope == "PLATFORM" else tenant_names.get(scope, "Seguradora")
        out.append({"kind": "FAILED_LOGINS", "severity": "WARNING", "tenantId": None if scope == "PLATFORM" else scope,
                    "title": f"{count} acessos falhados nas últimas 24 h",
                    "detail": f"{who} · {where}", "occurredAt": None})

    for account in StaffAccount.all_tenants.filter(locked_until__gt=now):
        out.append({"kind": "LOCKED_ACCOUNT", "severity": "WARNING", "tenantId": str(account.tenant_id),
                    "title": "Conta bloqueada",
                    "detail": f"{account.email} · {tenant_names.get(str(account.tenant_id), 'Seguradora')} · até {_when(account.locked_until)}",
                    "occurredAt": None})
    for admin in PlatformAdmin.objects.filter(locked_until__gt=now):
        out.append({"kind": "LOCKED_ACCOUNT", "severity": "WARNING", "tenantId": None,
                    "title": "Conta de super administrador bloqueada",
                    "detail": f"{admin.email} · até {_when(admin.locked_until)}", "occurredAt": None})

    legal_codes = [code for code, definition in DEFINITIONS.items() if definition.category == "LEGAL"]
    for event in PlatformAuditEvent.objects.filter(
        action__in=("platform_parameter.proposed", "platform_parameter.approved"),
        entity_id__in=legal_codes, occurred_at__gte=now - datetime.timedelta(days=LEGAL_DAYS),
    ).order_by("-occurred_at")[:20]:
        meta = event.metadata_json or {}
        verb = "aprovada" if event.action.endswith("approved") else "proposta"
        out.append({"kind": "LEGAL_PARAMETER", "severity": "INFO", "tenantId": None,
                    "title": f"Alteração legal {verb}: {event.entity_id}",
                    "detail": f"Valor {meta.get('value')} · {meta.get('legalReference') or 'sem referência legal'}",
                    "occurredAt": event.occurred_at})
    return out
