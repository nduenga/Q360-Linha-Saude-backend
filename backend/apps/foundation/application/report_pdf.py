"""PDF dos relatórios de análise, com a identidade visual da seguradora.

Usa o mesmo desenho dos outros documentos (`proposal_layout.render_pdf`). Os
dados chegam já calculados pelos relatórios em ecrã, para o PDF nunca mostrar
números diferentes dos da página.
"""
from __future__ import annotations

import datetime
from typing import Any
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.business_config.application.branding import branding_from, load_logo
from apps.business_config.application.readers import BusinessSnapshot
from apps.foundation.infrastructure.models import Tenant
from apps.quote.application.proposal_layout import render_pdf
from shared import formatting

STATUS_LABEL = {
    "DRAFT": "Rascunho", "READY": "Calculada", "IN_REVIEW": "Em análise", "APPROVED": "Aprovada",
    "BOUND": "Emitida", "REJECTED": "Rejeitada", "EXPIRED": "Expirada", "CANCELLED": "Cancelada",
    "ACTIVE": "Ativa", "PENDING_FIRST_PREMIUM": "Pendente do primeiro prémio", "SUSPENDED": "Suspensa",
    "TERMINATED": "Terminada", "RENEWED": "Renovada", "RESOLVED_BY_LAW": "Resolvida por falta de pagamento",
}
COVERAGE_TYPE = {"BASE": "Base", "COMPLEMENTARY": "Complementar"}
_EMPTY = "Sem dados neste período."
# O servidor corre em UTC; quem lê o relatório está em Angola.
_LUANDA = ZoneInfo("Africa/Luanda")


def _count(value: int) -> str:
    return formatting.number(value, digits=0)


def period_label(date_from: datetime.date | None, date_to: datetime.date | None) -> str:
    if date_from and date_to:
        return f"{formatting.date(date_from)} a {formatting.date(date_to)}"
    if date_from:
        return f"Desde {formatting.date(date_from)}"
    if date_to:
        return f"Até {formatting.date(date_to)}"
    return "Todo o período"


def generated_label() -> str:
    generated_at = timezone.now().astimezone(_LUANDA)
    return f"{formatting.date(generated_at)}, {generated_at:%H:%M}"


def insurer_name(tenant_id: Any) -> str:
    return Tenant.objects.filter(id=tenant_id).values_list("name", flat=True).first() or "Seguradora"


def _brand_blocks() -> list[tuple]:
    branding = branding_from(BusinessSnapshot.load())
    if branding and (branding.get("company") or branding.get("color")):
        return [("brand", {**branding, "logo": load_logo(branding)})]
    return []


def _table(header: list[str], rows: list[list[str]]) -> list[tuple]:
    return [("table", header, rows)] if rows else [("paragraph", _EMPTY)]


def _status_rows(rows: list[dict[str, Any]]) -> list[list[str]]:
    return [[STATUS_LABEL.get(row["status"], row["status"]), _count(row["count"])] for row in rows]


def _top_products_body(rows: list[dict[str, Any]]) -> list[tuple]:
    return _table(
        ["Produto", "Cotações", "Emitidas"],
        [[row["productName"], _count(row["quoteCount"]), _count(row["issuedCount"])] for row in rows],
    )


def _top_coverages_body(rows: list[dict[str, Any]]) -> list[tuple]:
    return _table(
        ["Cobertura", "Tipo", "Planos cotados"],
        [[row["benefitName"], COVERAGE_TYPE.get(row["category"], row["category"]), _count(row["planCount"])] for row in rows],
    )


def _issuance_body(data: dict[str, Any]) -> list[tuple]:
    return [
        ("kv", [("Cotações no período", _count(data["totalQuotes"])), ("Apólices no período", _count(data["totalPolicies"]))]),
        ("heading", "Cotações por estado"),
        *_table(["Estado", "Quantidade"], _status_rows(data["quotesByStatus"])),
        ("heading", "Apólices por estado"),
        *_table(["Estado", "Quantidade"], _status_rows(data["policiesByStatus"])),
    ]


# slug da rota -> (título, nome do ficheiro sem extensão, nota sobre o período, corpo do PDF)
REPORTS = {
    "top-products": ("Produtos mais cotados", "produtos-mais-cotados",
                     "Período pela data de criação da cotação.", _top_products_body),
    "top-coverages": ("Coberturas mais procuradas", "coberturas-mais-procuradas",
                      "Período pela data de criação da cotação.", _top_coverages_body),
    "issuance": ("Cotações e apólices emitidas", "cotacoes-e-apolices",
                 "Cotações pela data de criação e apólices pela data de início.", _issuance_body),
}


def render_report(slug: str, data: Any, *, tenant_id: Any, date_from: datetime.date | None,
                  date_to: datetime.date | None) -> tuple[bytes, str]:
    title, filename, period_note, body = REPORTS[slug]
    blocks = [
        *_brand_blocks(),
        ("title", title),
        ("kv", [
            ("Seguradora", insurer_name(tenant_id)),
            ("Período", period_label(date_from, date_to)),
            ("Gerado em", generated_label()),
        ]),
        *body(data),
        ("note", period_note),
    ]
    return render_pdf(blocks, title=title), f"{filename}.pdf"
