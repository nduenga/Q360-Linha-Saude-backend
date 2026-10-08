"""Apólice digital e documentos de cliente (declaração, comprovativo).

A apólice é montada a partir da cotação aprovada (coberturas, capitais,
franquia/participação, carências, exclusões, prémio) e dos dados de emissão
(assinatura, pagamento, prestações). Reutiliza os blocos e renderizadores da
proposta — HTML, PDF e DOCX dizem sempre o mesmo.

Ao emitir, o PDF é gravado (`MEDIA_ROOT/policies/<id>.pdf`) e passa a ser
servido tal e qual; sem ficheiro, gera-se na hora.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Callable

from django.conf import settings
from django.utils import timezone

from apps.business_config.application.branding import load_logo
from apps.client.infrastructure.models import InsuredMember
from apps.policy.domain.errors import PolicyStateError, ReferencedEntityNotFoundError
from apps.policy.infrastructure.models import Policy, PolicyMember, PolicySignature, PremiumInstallment
from apps.quote.application import proposal_content, proposal_layout

STATUS_TEXT = {
    "PENDING_FIRST_PREMIUM": "A aguardar o pagamento da 1.ª prestação",
    "ACTIVE": "Em vigor",
    "SUSPENDED": "Suspensa",
    "TERMINATED": "Terminada",
    "CANCELLED": "Cancelada",
    "EXPIRED": "Expirada",
    "RENEWED": "Renovada",
}
FREQUENCY_TEXT = {"ANUAL": "Anual", "SEMESTRAL": "Semestral", "TRIMESTRAL": "Trimestral", "MENSAL": "Mensal"}
CAPACITY_TEXT = {"TOMADOR": "Tomador", "REPRESENTANTE_LEGAL": "Representante legal", "PROCURADOR": "Procurador"}
PAYMENT_METHOD_TEXT = {"NUMERARIO": "Numerário", "TRANSFERENCIA": "Transferência bancária", "MULTICAIXA": "Multicaixa", "TPA": "TPA"}
STATEMENT_KINDS = ("COVERAGE", "PAYMENT")


def _render_preview() -> Callable:
    from apps.pricing.interfaces.serializers import render_preview  # lazy: interfaces layer

    return render_preview


def _day(value) -> str:
    if value is None:
        return "—"
    return value.date().isoformat() if isinstance(value, datetime.datetime) else value.isoformat()


def _policy_content(policy: Policy) -> dict[str, Any]:
    quote = policy.source_quote
    run = quote.latest_pricing_run
    if run is None:
        raise PolicyStateError(f"Policy {policy.id} has no priced quote to build the document from")
    calculation = _render_preview()(run)
    return proposal_content.build_content(
        quote=quote, scenario=None, calculation=calculation, generated_on=timezone.now().date()
    )


def _member_names(policy: Policy) -> list[tuple[PolicyMember, InsuredMember]]:
    members = list(policy.members.select_related("member").order_by("created_at", "id"))
    return [(pm, pm.member) for pm in members]


def _brand_block(content: dict[str, Any]) -> list[tuple]:
    branding = content.get("branding")
    if branding and (branding.get("company") or branding.get("color")):
        return [("brand", {**branding, "logo": load_logo(branding)})]
    return []


def _installments(policy: Policy) -> list[PremiumInstallment]:
    return list(PremiumInstallment.objects.filter(policy=policy).exclude(status="VOID").order_by("installment_no"))


def _installment_total(installments: list[PremiumInstallment]):
    return sum((i.amount for i in installments), start=0)


def policy_blocks(policy: Policy) -> tuple[list[tuple], str]:
    content = _policy_content(policy)
    currency = content["meta"]["currency"]
    holder, plan = content["client"], content["plan"]
    signature = PolicySignature.objects.filter(policy=policy).first()
    installments = _installments(policy)
    first_paid = next((i for i in installments if i.installment_no == 1 and i.status == "PAID"), None)
    total = _installment_total(installments)

    title = f"Apólice de Seguro de Saúde {policy.policy_number}"
    blocks: list[tuple] = _brand_block(content)
    blocks += [
        ("title", title),
        (
            "paragraph",
            "A presente apólice titula o contrato de seguro de saúde celebrado entre a seguradora e o tomador abaixo "
            "identificado, nos termos das condições particulares aqui descritas e das condições gerais aplicáveis.",
        ),
        ("heading", "Condições particulares"),
        (
            "kv",
            [
                ("Apólice n.º", policy.policy_number or "—"),
                ("Estado", STATUS_TEXT.get(policy.status, policy.status)),
                ("Tipo de apólice", "Grupo" if policy.policy_type == "GROUP" else "Individual / Familiar"),
                ("Tomador do seguro", holder["name"]),
                ("NIF / Identificação", holder["nif"] or "—"),
                ("Contactos", " · ".join(x for x in (holder["email"], holder["phone"]) if x) or "—"),
                ("Produto", plan["product"]),
                ("Plano", plan["name"]),
                ("Cotação de origem", content["meta"]["quoteNumber"] or "—"),
                ("Data de emissão", _day(policy.issued_at)),
                ("Início de vigência", _day(policy.start_date) if policy.start_date else "A definir após o pagamento"),
                ("Fim de vigência", _day(policy.end_date) if policy.end_date else "A definir após o pagamento"),
                ("Duração", f"{policy.term_months} meses"),
                ("Fracionamento do prémio", FREQUENCY_TEXT.get(policy.payment_frequency, policy.payment_frequency)),
                ("Moeda", currency),
                ("Prémio total", proposal_content.money(total, currency) if installments else content["premium"]["totalText"]),
            ],
        ),
    ]

    by_member = {str(m.member_id): m for m, _ in _member_names(policy)}
    rows = []
    for person in content["population"]:
        pm = by_member.get(person["memberId"])
        if pm is None:
            continue
        rows.append(
            [
                person["name"], person["relationship"], "—" if person["age"] is None else str(person["age"]),
                {"ACTIVE": "Segura", "PENDING": "Pendente"}.get(pm.status, pm.status), _day(pm.inclusion_date) if pm.inclusion_date else "—",
            ]
        )
    blocks += [
        ("heading", "Pessoas seguras"),
        ("table", ["Pessoa segura", "Relação", "Idade", "Estado", "Início da cobertura"], rows),
    ]

    proposal_layout._coverages(content, blocks)
    proposal_layout._premium(content, blocks)

    if installments:
        blocks += [
            ("heading", "Plano de pagamento"),
            (
                "table",
                ["N.º", "Período", "Vencimento", "Valor", "Estado"],
                [
                    [
                        str(i.installment_no), f"{_day(i.period_from)} a {_day(i.period_to)}", _day(i.due_date),
                        proposal_content.money(i.amount, i.currency_code), "Paga" if i.status == "PAID" else "Por pagar",
                    ]
                    for i in installments
                ],
            ),
        ]
    if first_paid is not None:
        blocks += [
            ("heading", "Pagamento da 1.ª prestação"),
            (
                "kv",
                [
                    ("Data do pagamento", _day(first_paid.paid_at)),
                    ("Meio de pagamento", PAYMENT_METHOD_TEXT.get(first_paid.payment_method or "", first_paid.payment_method or "—")),
                    ("Referência", first_paid.payment_reference or "—"),
                ],
            ),
        ]

    proposal_layout._waiting(content, blocks)
    proposal_layout._preexisting(content, blocks)
    proposal_layout._exclusions(content, blocks)
    proposal_layout._conditions(content, blocks)

    if signature is not None:
        blocks += [
            ("heading", "Assinatura do contrato"),
            (
                "kv",
                [
                    ("Signatário", signature.signatory_name),
                    ("Documento", f"{signature.signatory_document_type} {signature.signatory_document_number}"),
                    ("Qualidade", CAPACITY_TEXT.get(signature.signatory_capacity, signature.signatory_capacity)),
                    ("Modalidade", "Presencial" if signature.signature_method == "PRESENCIAL" else signature.signature_method),
                    ("Data da assinatura", _day(signature.signed_at)),
                ],
            ),
        ]
    blocks.append(("signature", ["O Tomador", "A Seguradora"]))
    if content.get("disclaimer"):
        blocks.append(("note", content["disclaimer"]))
    branding = content.get("branding")
    if branding and branding.get("footer"):
        blocks.append(("note", branding["footer"]))
    return blocks, title


# ---------------------------------------------------------------- statements
def statement_blocks(policy: Policy, *, kind: str, installment_no: int | None) -> tuple[list[tuple], str]:
    if kind not in STATEMENT_KINDS:
        raise ReferencedEntityNotFoundError(f"kind must be one of {list(STATEMENT_KINDS)}")
    content = _policy_content(policy)
    holder, plan = content["client"], content["plan"]
    today = timezone.now().date().isoformat()
    blocks: list[tuple] = _brand_block(content)

    if kind == "COVERAGE":
        if policy.status != "ACTIVE":
            raise PolicyStateError(f"Policy {policy.policy_number} is {policy.status}; a coverage statement needs an ACTIVE policy")
        title = f"Declaração de cobertura — apólice {policy.policy_number}"
        names = {p["memberId"]: p["name"] for p in content["population"]}
        people = [[names.get(str(pm.member_id), "—"), _day(pm.inclusion_date)] for pm, _ in _member_names(policy) if pm.status == "ACTIVE"]
        blocks += [
            ("title", title),
            (
                "paragraph",
                f"Declara-se que a apólice n.º {policy.policy_number}, de que é tomador {holder['name']}, se encontra em vigor "
                f"de {_day(policy.start_date)} a {_day(policy.end_date)}, no plano {plan['name']} ({plan['product']}), "
                "garantindo as pessoas seguras abaixo indicadas, nas condições da apólice.",
            ),
            ("table", ["Pessoa segura", "Início da cobertura"], people),
            ("note", f"Declaração emitida eletronicamente em {today}, a pedido do tomador. Não substitui as condições da apólice."),
        ]
        return blocks, title

    installment = (
        PremiumInstallment.objects.filter(policy=policy, installment_no=installment_no, status="PAID").first()
        if installment_no
        else PremiumInstallment.objects.filter(policy=policy, status="PAID").order_by("-installment_no").first()
    )
    if installment is None:
        raise ReferencedEntityNotFoundError("No paid installment found for this payment receipt")
    title = f"Comprovativo de pagamento — apólice {policy.policy_number}"
    blocks += [
        ("title", title),
        (
            "kv",
            [
                ("Apólice n.º", policy.policy_number or "—"),
                ("Tomador", holder["name"]),
                ("NIF / Identificação", holder["nif"] or "—"),
                ("Prestação", f"{installment.installment_no} ({FREQUENCY_TEXT.get(policy.payment_frequency, policy.payment_frequency)})"),
                ("Período coberto", f"{_day(installment.period_from)} a {_day(installment.period_to)}"),
                ("Valor pago", proposal_content.money(installment.amount, installment.currency_code)),
                ("Data do pagamento", _day(installment.paid_at)),
                ("Meio de pagamento", PAYMENT_METHOD_TEXT.get(installment.payment_method or "", installment.payment_method or "—")),
                ("Referência", installment.payment_reference or "—"),
            ],
        ),
        ("note", f"Comprovativo emitido eletronicamente em {today}."),
    ]
    return blocks, title


# ------------------------------------------------------------------- render
def _render(blocks: list[tuple], title: str, fmt: str) -> tuple[bytes, str, str]:
    fmt = fmt.upper()
    if fmt not in proposal_layout.RENDERERS:
        raise ReferencedEntityNotFoundError(f"format must be one of {list(proposal_layout.RENDERERS)}")
    renderer, content_type, ext = proposal_layout.RENDERERS[fmt]
    return renderer(blocks, title=title), content_type, ext


def _safe(number: str | None) -> str:
    return (number or "apolice").replace("/", "-").replace(" ", "")


def _stored_path(policy: Policy) -> Path:
    return Path(settings.MEDIA_ROOT) / "policies" / f"{policy.id}.pdf"


def store_policy_document(policy: Policy) -> Path:
    """Grava o PDF da apólice (chamado ao emitir e ao activar)."""
    blocks, title = policy_blocks(policy)
    data, _, _ = _render(blocks, title, "PDF")
    path = _stored_path(policy)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def policy_document(policy: Policy, fmt: str = "PDF") -> tuple[bytes, str, str]:
    """(bytes, content_type, file_name) da apólice digital."""
    if fmt.upper() == "PDF" and _stored_path(policy).exists():
        return _stored_path(policy).read_bytes(), "application/pdf", f"apolice-{_safe(policy.policy_number)}.pdf"
    blocks, title = policy_blocks(policy)
    data, content_type, ext = _render(blocks, title, fmt)
    return data, content_type, f"apolice-{_safe(policy.policy_number)}.{ext}"


def statement_document(policy: Policy, *, kind: str, installment_no: int | None = None) -> tuple[bytes, str, str]:
    blocks, title = statement_blocks(policy, kind=kind, installment_no=installment_no)
    data, content_type, _ = _render(blocks, title, "PDF")
    prefix = "declaracao-cobertura" if kind == "COVERAGE" else "comprovativo-pagamento"
    return data, content_type, f"{prefix}-{_safe(policy.policy_number)}.pdf"
