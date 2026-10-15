"""Teste de referência SAG (decisão A4): o backend reproduz o `Calculador`
do Excel com `C5 = SAG` e as restantes entradas do próprio ficheiro
(Conforto -> Quadros Médios, Luanda, co-pagamento 5 000 Kz, comparticipação
80 %, 40 colaboradores, adesão obrigatória, Comércio e Serviços; as mesmas 4
pessoas e opcionais do cenário SAU).

O Excel só guarda os valores do cenário SAU; os valores esperados SAG vêm do
recálculo das fórmulas do próprio livro (`tools/recalc_calculador.py`, ver a
proveniência no ficheiro de fixture). O prémio é por colaborador-tipo com o
seu agregado (C86); a apólice SAG do Excel multiplica pelo n.º de
colaboradores (C87), e o backend soma as pessoas reais (decisão A3).
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from apps.business_config.seed.actuarial_model import build_actuarial_model
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId
from apps.policy.application.issuance_service import installment_amount
from apps.quote.infrastructure.models import Quote
from tests.quote.conftest import make_client
from tests.quote.test_actuarial_excel_reference import EFFECTIVE_DATE, PEOPLE
from tests.quote.test_business_config_e2e import SCOPE, _publish, _values

EXPECTED = json.loads((Path(__file__).parent / "fixtures" / "calculador_sag_expected.json").read_text())["cells"]


def _d(cell: str) -> Decimal:
    return Decimal(str(EXPECTED[cell]))


@pytest.fixture
def approver(tenant):
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPE, actor_id="approver-1")


@pytest.mark.django_db
def test_backend_reproduces_the_excel_calculador_for_sag(admin_client, approver, tenant):
    assert EXPECTED["C7"] == "Quadros Médios"
    market = admin_client.post("/api/v1/product-templates/market", {}, format="json")
    assert market.status_code == 200, market.data
    plan = {p["code"]: p for p in admin_client.get("/api/v1/plans?size=50").data["items"]}["GRP-QUADROS"]
    for key, value in _values("1").items():
        _publish(admin_client, approver, key, value)
    _publish(admin_client, approver, "pricing.actuarial_model", build_actuarial_model())
    rule = admin_client.post(
        "/api/v1/rule-versions",
        {"code": "ELIG-XLS-SAG", "name": "Eligibility", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps({})},
        format="json",
    ).data
    admin_client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")

    proposer = admin_client.post(
        "/api/v1/proposers",
        {"proposerType": "ORGANISATION", "displayName": "Empresa Calculador", "registrationNumber": "5417000001",
         "email": "rh@example.com", "phone": "+244900000000",
         "attributes": {"actuarialProfile": {
             "region": "Luanda (Grande Luanda)",
             "costSharing": {"copaymentAoa": 5000, "reimbursementShare": "0.8",
                             "outpatientDeductibleAoa": 0, "inpatientDeductibleAoa": 0},
             "crossSell": "Nenhuma",
             "industry": "Comércio e Serviços", "adhesion": "MANDATORY", "groupHeadcount": 40,
         }}},
        format="json",
    )
    assert proposer.status_code == 201, proposer.data
    quote = admin_client.post(
        "/api/v1/quotes", {"proposerId": proposer.data["id"], "planId": plan["id"], "effectiveDate": EFFECTIVE_DATE},
        format="json",
    ).data
    member_cells = {}
    for relationship, sex, birth, cell in PEOPLE:
        member = admin_client.post(
            "/api/v1/members",
            {"proposerId": proposer.data["id"], "relationshipCode": relationship, "sexCode": sex, "dateOfBirth": birth},
            format="json",
        )
        assert member.status_code == 201, member.data
        member_cells[member.data["id"]] = cell
        added = admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member.data["id"]}, format="json")
        assert added.status_code in (200, 201), added.data
    # Opcionais do Excel: Medicamentos e Estomatologia (a Maternidade é base em Quadros
    # Médios). As doenças endémicas (MAL) são base na Matriz_SAG e opcionais no plano
    # de mercado (PDF, que prevalece — decisão A2): escolhem-se para igualar o cenário.
    current = admin_client.get(f"/api/v1/quotes/{quote['id']}").data
    selected = admin_client.put(
        f"/api/v1/quotes/{quote['id']}/selection",
        {"selection": {"optionalBenefitCodes": ["PHARMACY", "DENTAL", "ENDEMIC_DISEASES"]},
         "rowVersion": current["rowVersion"]},
        format="json",
    )
    assert selected.status_code == 200, selected.data

    priced = admin_client.post(f"/api/v1/quotes/{quote['id']}/price", {"recalculate": True}, format="json")
    assert priced.status_code == 200, priced.data
    components = priced.data["components"]

    # 1. Prémio puro base por pessoa (K25:K28): sem agravamento de adesão em SAG (J = 0)
    for member_id, cell in member_cells.items():
        base = sum(Decimal(c["baseAmount"]) for c in components
                   if c["memberId"] == member_id and c["code"].startswith("ACTUARIAL_") and c["type"] == "BASE")
        assert abs(base - _d(cell)) <= Decimal("0.10"), (cell, base, _d(cell))
    assert not any(c["code"] == "ACTUARIAL_ENTRY_AGE_LOADING" for c in components)

    # 2. Factor de risco (C64: participação × região × dimensão × adesão × sector) e sem desconto (C70 = 0)
    risk = {c["factorValue"] for c in components if c["code"] == "ACTUARIAL_RISK_FACTOR"}
    assert len(risk) == 1 and abs(Decimal(risk.pop()) - _d("C64")) < Decimal("0.0000001")
    assert not any(c["code"] == "ACTUARIAL_COMMERCIAL_DISCOUNT" for c in components)

    # 3. Impostos (C85) e prémio anual do colaborador-tipo com o seu agregado (C86)
    taxes = sum(Decimal(c["adjustmentAmount"]) for c in components if c["code"] in {"STAMP_DUTY", "ARSEG_LEVY"})
    assert abs(taxes - _d("C85")) <= Decimal("0.05"), (taxes, _d("C85"))
    total = Decimal(priced.data["totalAmount"])
    assert abs(total - _d("C86")) <= Decimal("0.10"), (total, _d("C86"))

    # 4. Prestações com encargo de fracionamento (E91:E94)
    token = CurrentActorProvider.bind(Actor(actor_id="test", tenant_id=TenantId(tenant.id), roles=frozenset()))
    try:
        quote_row = Quote.objects.select_related("latest_pricing_run").get(id=quote["id"])
        for frequency, cell in (("ANUAL", "E91"), ("SEMESTRAL", "E92"), ("TRIMESTRAL", "E93"), ("MENSAL", "E94")):
            amount = installment_amount(quote_row, total, frequency)
            assert abs(amount - _d(cell)) <= Decimal("0.10"), (frequency, amount, _d(cell))
    finally:
        CurrentActorProvider.reset(token)
