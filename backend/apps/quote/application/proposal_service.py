"""Geração de propostas (R8) a partir da cotação ou de um cenário.

  - sem `scenarioId`: usa o cenário **selecionado** da cotação; se não houver,
    o estado atual da cotação (cálculo fresco);
  - um cenário desatualizado (plano/tarifas/população mudaram) não gera
    proposta: tem de ser recalculado primeiro;
  - formatos PDF, DOCX e HTML, todos a partir do mesmo conteúdo estruturado
    (`proposal_content` + `proposal_layout`) e de um modelo de documento
    editável pelo GTE (`proposal_template`);
  - o conteúdo fica num snapshot `DOCUMENT` da cotação: `retry` e auditoria
    reproduzem o documento sem recalcular;
  - se nenhum modelo `QUOTE_PROPOSAL_DEFAULT` estiver publicado, é criado e
    publicado o modelo por omissão (editável como qualquer outro).
"""
from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from django.conf import settings
from django.utils import timezone

from apps.foundation.application.audit_service import AuditService
from apps.foundation.application.change_audit import change_metadata
from apps.foundation.application.context import CurrentActorProvider, CurrentTenantProvider
from apps.foundation.application.outbox_service import get_outbox_service
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.infrastructure.audit_repository import DjangoAuditRepositoryAdapter
from apps.quote.application import (
    document_service,
    letterhead,
    proposal_content,
    proposal_layout,
    scenario_service,
    simulator_service,
    template_files,
    word_template,
)
from apps.quote.application.numbering_service import next_continuous_value
from apps.quote.domain.enums import DocumentStatus, DocumentType, QuoteSnapshotType, QuoteStatus
from apps.quote.domain.errors import QuoteStateError
from apps.quote.domain.proposal_template import DEFAULT_TEMPLATE, default_body, parse_template
from apps.quote.infrastructure.models import Document, DocumentTemplateVersion, Quote, QuoteScenario, QuoteSnapshot

_audit = AuditService(DjangoAuditRepositoryAdapter())
_outbox = get_outbox_service()
_BLOCKED = (QuoteStatus.CANCELLED.value, QuoteStatus.REJECTED.value, QuoteStatus.EXPIRED.value)
FORMATS = tuple(proposal_layout.RENDERERS)


class ProposalError(DomainProblem):
    http_status = 409
    problem_code = "CONFLICT"


class ProposalRequestError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


class DocumentNotFoundError(DomainProblem):
    http_status = 404
    problem_code = "NOT-FOUND"


def resolve_template(*, code: str, effective_date: datetime.date) -> DocumentTemplateVersion:
    template = document_service.resolve_template_for(template_code=code, effective_date=effective_date)
    if template is not None:
        return template
    if code != document_service.DEFAULT_TEMPLATE_CODE:
        raise document_service.TemplateNotFoundError(document_service.template_not_found_message(template_code=code, effective_date=effective_date))
    created = document_service.create_document_template(
        template_code=code, storage_ref=default_body(), effective_from=datetime.date(2020, 1, 1)
    )
    return document_service.publish_document_template(created)


def _scenario_for(quote: Quote, scenario_id) -> QuoteScenario | None:
    if scenario_id:
        scenario = QuoteScenario.objects.filter(id=scenario_id, quote=quote).first()
        if scenario is None:
            raise ProposalRequestError(f"O cenário {scenario_id} não pertence à cotação {quote.id}")
        return scenario
    return QuoteScenario.objects.filter(quote=quote, is_selected=True).first()


def _content_for(quote: Quote, scenario: QuoteScenario | None, render: Callable) -> dict[str, Any]:
    if quote.status in _BLOCKED:
        raise QuoteStateError(f"A cotação {quote.id} está em {quote.status}; não é possível gerar a proposta")
    if scenario is not None:
        if scenario_service.is_stale(scenario):
            raise ProposalError(
                f"O cenário '{scenario.name}' está desatualizado (o plano, as tarifas ou as pessoas seguras mudaram): recalcule-o primeiro"
            )
        calculation = scenario.result_json
    else:
        calculation = simulator_service.preview_quote(quote=quote, selection=None, extra_adjustments=None, render=render)
    return proposal_content.build_content(
        quote=quote, scenario=scenario, calculation=calculation, generated_on=timezone.now().date()
    )


def preview(*, quote: Quote, scenario_id, template_code: str | None, fmt: str, render: Callable) -> tuple[bytes, str]:
    scenario = _scenario_for(quote, scenario_id)
    content = _content_for(quote, scenario, render)
    template = resolve_template(code=template_code or document_service.DEFAULT_TEMPLATE_CODE, effective_date=quote.effective_date)
    return _render(content, template, fmt, document_number=None)


def _render(content: dict[str, Any], template: DocumentTemplateVersion, fmt: str, *, document_number: str | None) -> tuple[bytes, str]:
    if fmt not in proposal_layout.RENDERERS:
        raise ProposalRequestError(f"O formato tem de ser um de {list(FORMATS)}")
    spec = parse_template(template.storage_ref)
    generated_on = content["meta"]["generatedOn"]
    variables = proposal_layout.variables_for(content, document_number=document_number, generated_on=generated_on)
    if fmt == "DOCX" and template.word_key:
        # Opção B: o Word do GTE com as marcas {{variável}} substituídas.
        client = content["client"]
        scalars = {
            **variables,
            "client.email": client.get("email"),
            "client.phone": client.get("phone"),
            "plan.accessSystem": content["plan"].get("accessSystem"),
        }
        data = word_template.fill(
            template_files.read_word(template), scalars=scalars, groups=word_template.groups_from_content(content)
        )
        return data, word_template.DOCX_CONTENT_TYPE
    blocks = proposal_layout.build_blocks(content, spec, variables)
    renderer, content_type, _ext = proposal_layout.RENDERERS[fmt]
    from apps.quote.domain.proposal_template import render_text

    title = render_text(spec["title"], variables)
    if fmt == "PDF":
        # Opção A: o texto cai dentro da área livre do papel timbrado do GTE.
        data = renderer(blocks, title=title, layout=template_files.layout_for(template))
        letter = template_files.read_letterhead(template)
        return (letterhead.apply(data, letter) if letter else data), content_type
    return renderer(blocks, title=title), content_type


def generate(
    *, quote: Quote, template_code: str | None, scenario_id, fmt: str, render: Callable
) -> Document:
    if fmt not in proposal_layout.RENDERERS:
        raise ProposalRequestError(f"O formato tem de ser um de {list(FORMATS)}")
    scenario = _scenario_for(quote, scenario_id)
    content = _content_for(quote, scenario, render)
    template = resolve_template(code=template_code or document_service.DEFAULT_TEMPLATE_CODE, effective_date=quote.effective_date)

    actor = CurrentActorProvider.get()
    actor_id = actor.actor_id if actor else "unknown"
    tenant_id = CurrentTenantProvider.require()
    snapshot_json = {"type": "PROPOSAL", "content": content, "templateCode": template.template_code, "templateVersion": template.version_no}
    snapshot_no = (QuoteSnapshot.objects.filter(quote=quote).order_by("-snapshot_no").values_list("snapshot_no", flat=True).first() or 0) + 1
    snapshot = QuoteSnapshot.objects.create(
        tenant_id=quote.tenant_id, quote=quote, snapshot_no=snapshot_no, snapshot_type=QuoteSnapshotType.DOCUMENT.value,
        pricing_run=quote.latest_pricing_run, plan=quote.plan, snapshot_json=snapshot_json,
        checksum=hashlib.sha256(json.dumps(snapshot_json, sort_keys=True).encode("utf-8")).hexdigest(), created_by=actor_id,
    )
    proposal_no = (Document.objects.filter(quote=quote).count()) + 1
    document = Document.objects.create(
        tenant_id=tenant_id.value, quote=quote, snapshot=snapshot, template_version=template,
        document_type=DocumentType.QUOTE_PROPOSAL.value, status=DocumentStatus.REQUESTED.value,
        requested_by=actor_id, format=fmt, scenario_id=scenario.id if scenario else None, proposal_no=proposal_no,
    )
    _outbox.append(
        aggregate_type="Document", aggregate_id=str(document.id), event_type="DOCUMENT.GENERATION.REQUESTED",
        payload={"documentId": str(document.id), "quoteId": str(quote.id), "documentType": "QUOTE_PROPOSAL", "requestedBy": actor_id, "format": fmt},
    )
    return _produce(document=document, content=content, template=template, quote=quote)


def _produce(*, document: Document, content: dict[str, Any], template: DocumentTemplateVersion, quote: Quote) -> Document:
    try:
        number = document.document_number or next_continuous_value(sequence_code="QUOTE_PROPOSAL")
        data, content_type = _render(content, template, document.format, document_number=number)
        ext = proposal_layout.RENDERERS[document.format][2]
        directory = Path(settings.MEDIA_ROOT) / "documents"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{document.id}.{ext}"
        path.write_bytes(data)
        Document.objects.filter(id=document.id).update(
            status=DocumentStatus.GENERATED.value, storage_ref=str(path), checksum=hashlib.sha256(data).hexdigest(),
            document_number=number, generated_at=timezone.now(), content_type=content_type,
            file_name=f"Proposta-{quote.quote_number}-{document.proposal_no}.{ext}", failure_code=None,
        )
    except Exception as exc:  # noqa: BLE001 - any rendering failure is recorded on the document
        Document.objects.filter(id=document.id).update(
            status=DocumentStatus.FAILED.value, failure_code=str(exc)[:100], generated_at=timezone.now()
        )
        _audit.record(
            action="document.generation_failed", entity_type="Document", entity_id=str(document.id),
            metadata={"result": "FAILURE", "reason": str(exc)[:200]},
        )
        document.refresh_from_db()
        return document
    document.refresh_from_db()
    _audit.record(
        action="document.generated", entity_type="Document", entity_id=str(document.id),
        metadata=change_metadata(after={"documentNumber": document.document_number, "format": document.format,
                                        "scenarioId": str(document.scenario_id) if document.scenario_id else None},
                                 quoteId=str(quote.id), checksum=document.checksum),
    )
    _outbox.append(
        aggregate_type="Document", aggregate_id=str(document.id), event_type="DOCUMENT.GENERATED",
        payload={"documentId": str(document.id), "quoteId": str(quote.id), "documentNumber": document.document_number, "format": document.format},
    )
    return document


def retry(*, document: Document) -> Document:
    if document.status != DocumentStatus.FAILED.value:
        raise ProposalError(f"O documento {document.id} está em {document.status}; só um documento com falha (FAILED) pode ser repetido")
    content = document.snapshot.snapshot_json["content"]
    return _produce(document=document, content=content, template=document.template_version, quote=document.quote)


def list_documents(*, quote: Quote):
    return Document.objects.filter(quote=quote).order_by("-requested_at", "-proposal_no")


def get_document(document_id) -> Document:
    document = Document.objects.select_related("quote", "snapshot", "template_version").filter(id=document_id).first()
    if document is None:
        raise DocumentNotFoundError(f"O documento {document_id} não existe")
    return document


def read_file(document: Document) -> bytes:
    if document.status != DocumentStatus.GENERATED.value or not document.storage_ref:
        raise ProposalError(f"O documento {document.id} não tem ficheiro gerado ({document.status})")
    data = Path(document.storage_ref).read_bytes()
    if hashlib.sha256(data).hexdigest() != document.checksum:
        raise ProposalError(f"O documento {document.id} falhou a verificação de integridade (checksum não coincide)")
    return data


def sample_content() -> dict[str, Any]:
    """Synthetic content to preview a template layout before publishing."""
    return {
        "meta": {"quoteId": "00000000-0000-0000-0000-000000000000", "quoteNumber": "COT-EXEMPLO", "quoteType": "Novo negócio",
                 "effectiveDate": "2026-01-01", "validUntil": "2026-01-31", "generatedOn": "2026-01-01", "currency": "AOA", "scenario": None},
        "client": {"name": "Cliente de Exemplo, Lda.", "nif": "5417000000", "email": None, "phone": None},
        "plan": {"product": "Saúde Grupo (Empresas)", "name": "Grupo — Quadros", "segment": "Grupo (Empresas)", "tier": "À medida",
                 "category": "Quadros", "accessSystem": "Misto: rede em Angola; reembolso fora da rede ou no estrangeiro"},
        "population": [{"memberId": "x", "name": "Pessoa Exemplo", "relationship": "Titular", "age": 40, "status": "INCLUDED",
                        "clinicalQuestionnaireRequired": False, "medicalExamRequired": False, "preExisting": None}],
        "coverages": [{"code": "HOSPITALIZATION", "name": "Hospitalização", "category": "BASE", "inclusion": "INCLUDED", "contracted": True,
                       "limits": ["Capital anual por pessoa: 25.000.000 Kz"], "participation": ["Rede convencionada: sem participação do segurado"],
                       "waiting": "sem carência", "requiresPriorApproval": False, "destinations": [], "closedDiseaseList": [], "currency": "AOA",
                       "maxDaysPerYear": None, "timeDeductibleDays": None, "excludedItems": [], "notes": None, "indicative": True}],
        "participationOption": None,
        "premium": {"total": "100000.00", "totalText": "100.000 Kz", "currency": "AOA",
                    "members": [{"memberId": "x", "name": "Pessoa Exemplo", "total": "100000.00", "lines": []}],
                    "quoteLevel": [], "adjustments": [], "warnings": []},
        "waiting": [{"coverage": "Hospitalização", "text": "sem carência"}],
        "preExisting": {"defaultTreatment": "Aceitação integral: coberta como qualquer outra doença.", "decisions": []},
        "exclusions": ["Cirurgia plástica ou estética, salvo reconstrutiva após acidente ou doença coberta"],
        "conditions": ["Não há regra de rateio: esgotado o capital anual, a seguradora deixa de pagar até à anuidade seguinte."],
        "disclaimer": DEFAULT_TEMPLATE["disclaimer"],
    }


def _sample_policy_word_data(content: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Valores de exemplo para pré-visualizar um modelo Word de apólice."""
    client, plan = content["client"], content["plan"]
    scalars = {
        "client.name": client["name"], "client.nif": client["nif"], "client.email": "cliente@exemplo.ao", "client.phone": "+244 900 000 000",
        "plan.name": plan["name"], "plan.product": plan["product"], "plan.segment": plan["segment"], "plan.accessSystem": plan["accessSystem"],
        "premium.total": content["premium"]["totalText"], "premium.currency": "AOA",
        "document.number": "APO-EXEMPLO", "document.date": "2026-01-01", "insured.count": len(content["population"]),
        "quote.number": content["meta"]["quoteNumber"], "policy.number": "APO-EXEMPLO", "policy.status": "Em vigor",
        "policy.type": "Grupo", "policy.issueDate": "2026-01-01", "policy.startDate": "2026-01-02", "policy.endDate": "2027-01-01",
        "policy.termMonths": 12, "policy.paymentFrequency": "Trimestral", "policy.totalPremium": content["premium"]["totalText"],
        "signature.name": "Pessoa Exemplo", "signature.document": "BI 000000000LA000", "signature.capacity": "Tomador",
        "signature.date": "2026-01-01", "payment.firstDate": "2026-01-01", "payment.firstMethod": "Transferência bancária",
        "payment.firstReference": "TRF-EXEMPLO",
    }
    groups = word_template.groups_from_content(content)
    groups["installment"] = [
        {"no": n, "period": f"2026-0{n}-02 a 2026-0{n + 2}-01", "dueDate": f"2026-0{n}-02", "amount": "25.000 Kz", "status": "Por pagar"}
        for n in (1, 4, 7)
    ]
    return scalars, groups


def preview_template(*, template: DocumentTemplateVersion, fmt: str = "HTML") -> tuple[bytes, str]:
    content = sample_content()
    if template.document_type == "POLICY" and fmt == "DOCX" and template.word_key:
        scalars, groups = _sample_policy_word_data(content)
        return word_template.fill(template_files.read_word(template), scalars=scalars, groups=groups), word_template.DOCX_CONTENT_TYPE
    return _render(content, template, fmt, document_number="DOC-EXEMPLO")
