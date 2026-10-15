"""Configuração de tarifação por produto, como nos ecrãs do produto: grupos de
opções, campos, «Taxas e Valores» (Simples, Múltiplas opções, Fixo, Por
intervalo de idade, Pelo valor do campo, Condicional de opção) e fórmulas
(Prémio, Capital, Ocultar, Fracionamento, resultado mínimo, âmbito), com
rascunho, aprovação por outra pessoa, teste e histórico — e o efeito numa
cotação."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from tests.quote.test_business_config_e2e import BASE, _publish_all, approver  # noqa: F401  (fixture)
from tests.quote.test_quotes import _member, _plan, _proposer

# O exemplo das imagens (Acidentes de Trabalho): actividade × massa salarial × multiplicador.
SETUP = {
    "optionGroups": [
        {"code": "actividade", "name": "Actividade da empresa ou CAE", "listType": "SELECT", "required": True,
         "options": [{"code": "comercio", "label": "Comércio"}, {"code": "construcao", "label": "Construção"}]},
        {"code": "multiplicador", "name": "Multiplicar com Massa Salarial", "listType": "CHECKBOX",
         "options": [{"code": "base", "label": "Base"}, {"code": "extra", "label": "Extra"}]},
        {"code": "modalidade", "name": "Modalidade de Pagamento do Seguro", "listType": "RADIO",
         "options": [{"code": "anual", "label": "Anual"}, {"code": "semestral", "label": "Semestral"},
                     {"code": "trimestral", "label": "Trimestral"}]},
        {"code": "faixa", "name": "Faixa etária", "listType": "RADIO", "showInForm": False,
         "options": [{"code": "todas", "label": "Todas"}]},
    ],
    "fields": [{"code": "massa_salarial", "label": "Massa Salarial", "type": "NUMBER", "required": True, "min": "0", "unit": "AOA"}],
    "values": [
        {"group": "actividade", "type": "SIMPLE", "unit": "PERCENT",
         "rows": [{"option": "comercio", "value": "0.02"}, {"option": "construcao", "value": "0.05"}]},
        {"group": "multiplicador", "type": "SIMPLE", "aggregate": "SUM",
         "rows": [{"option": "base", "value": "1"}, {"option": "extra", "value": "0.5"}]},
        {"group": "faixa", "type": "AGE_INTERVAL", "aggregate": "SUM",
         "rows": [{"ageFrom": 0, "ageTo": 39, "value": "100"}, {"ageFrom": 40, "ageTo": 150, "value": "300"}]},
    ],
    "formulas": [
        {"code": "premio_anual", "name": "Prémio anual",
         "expression": "premio_tecnico + actividade * massa_salarial * multiplicador + faixa",
         "flags": {"premium": True}, "minResult": "1000", "order": 1},
        {"code": "premio_semestral", "name": "Prémio semestral", "expression": "premio_anual / 2",
         "flags": {"fractionation": True}, "frequency": "SEMESTRAL", "order": 2},
        {"code": "taxa_total", "name": "Taxa total", "expression": "actividade", "unit": "PERCENT", "order": 5},
        {"code": "taxa_simples", "name": "Taxa simples", "expression": "taxa_total * 1.2", "unit": "PERCENT",
         "flags": {"hidden": True}, "order": 6},
    ],
}


def _publish_setup(client, approver, product_id, value=SETUP):  # noqa: F811
    saved = client.put(f"/api/v1/products/{product_id}/pricing-setup", {"value": value, "effectiveFrom": "2026-01-01"}, format="json")
    assert saved.status_code == 200, saved.data
    assert client.post(f"{BASE}/{saved.data['id']}", {"action": "submit"}, format="json").status_code == 200
    approved = approver.post(f"{BASE}/{saved.data['id']}/approve")
    assert approved.status_code == 200, approved.data
    return saved.data


def _priced_scope(client, approver, product_code):  # noqa: F811
    plan_ref = _plan(client, product_code=product_code)
    proposer_id = _proposer(client)
    member_id = _member(client, proposer_id=proposer_id, date_of_birth="1980-01-01")
    rule = client.post(
        "/api/v1/rule-versions",
        {"code": f"ELIG-{product_code}", "name": "Eligibility", "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps({})},
        format="json",
    ).data
    client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")
    _publish_all(client, approver, "100000", "2026-01-01")
    quote = client.post("/api/v1/quotes", {"proposerId": proposer_id, "planId": plan_ref["planId"]}, format="json").data
    client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")
    return {**plan_ref, "quote": quote}


def _select(client, quote_id, selection):
    current = client.get(f"/api/v1/quotes/{quote_id}").data
    return client.put(f"/api/v1/quotes/{quote_id}/selection",
                      {"selection": selection, "rowVersion": current["rowVersion"]}, format="json")


@pytest.mark.django_db
def test_the_product_setup_is_drafted_validated_approved_and_versioned(admin_client, approver):  # noqa: F811
    product_id = _plan(admin_client, product_code="SETUP-GOV")["productId"]
    assert admin_client.get(f"/api/v1/products/{product_id}/pricing-setup").data["published"] is None

    circular = {**SETUP, "formulas": [{"code": "a", "name": "A", "expression": "b + 1"}, {"code": "b", "name": "B", "expression": "a + 1"}]}
    refused = admin_client.put(f"/api/v1/products/{product_id}/pricing-setup", {"value": circular}, format="json")
    assert refused.status_code == 400 and "circular" in str(refused.data)
    unknown = {**SETUP, "formulas": [{"code": "x", "name": "X", "expression": "nao_existe * 2"}]}
    assert admin_client.post(f"/api/v1/products/{product_id}/pricing-setup/validate", {"value": unknown}, format="json").status_code == 400
    valid = admin_client.post(f"/api/v1/products/{product_id}/pricing-setup/validate", {"value": SETUP}, format="json")
    assert valid.status_code == 200 and valid.data["evaluationOrder"][0] == "premio_anual"
    assert {"actividade", "actividade__comercio", "massa_salarial", "premio_anual", "premio_tecnico"} <= {t["token"] for t in valid.data["tokens"]}

    draft = _publish_setup(admin_client, approver, product_id)
    state = admin_client.get(f"/api/v1/products/{product_id}/pricing-setup").data
    assert state["published"]["versionNo"] == 1 and state["draft"] is None
    assert [i["code"] for i in state["form"]["items"]] == ["actividade", "multiplicador", "modalidade", "massa_salarial"]
    # O criador não aprova a própria versão (quatro olhos).
    second = admin_client.put(f"/api/v1/products/{product_id}/pricing-setup", {"value": SETUP}, format="json").data
    admin_client.post(f"{BASE}/{second['id']}", {"action": "submit"}, format="json")
    assert admin_client.post(f"{BASE}/{second['id']}/approve").status_code == 403
    history = admin_client.get(f"/api/v1/products/{product_id}/pricing-setup/history").data["items"]
    assert [(h["versionNo"], h["status"]) for h in history] == [(2, "PENDING_APPROVAL"), (1, "PUBLISHED")]
    assert history[1]["id"] == draft["id"]


@pytest.mark.django_db
def test_test_formula_with_example_values(admin_client):
    product_id = _plan(admin_client, product_code="SETUP-TEST")["productId"]
    tested = admin_client.post(
        f"/api/v1/products/{product_id}/pricing-setup/test",
        {"value": SETUP, "productOptions": {"actividade": "construcao", "multiplicador": ["base", "extra"]},
         "productFields": {"massa_salarial": "1000000"}, "ages": [45], "technicalPremium": "0",
         "expression": "taxa_total * 100"},
        format="json",
    )
    assert tested.status_code == 200, tested.data
    results = {r["code"]: r for r in tested.data["results"]}
    assert results["premio_anual"]["value"] == "75300.00"  # 0,05 × 1 000 000 × 1,5 + 300
    assert results["premio_semestral"]["value"] == "37650.00"
    assert results["taxa_simples"]["flags"]["hidden"] is True
    assert tested.data["installments"] == {"SEMESTRAL": "37650.00"}
    assert Decimal(tested.data["expressionValue"]) == Decimal("5")
    assert tested.data["groupValues"]["multiplicador"] == "1.5"
    # Resultado mínimo.
    low = admin_client.post(f"/api/v1/products/{product_id}/pricing-setup/test",
                            {"value": SETUP, "productOptions": {"actividade": "comercio", "multiplicador": ["base"]},
                             "productFields": {"massa_salarial": "100"}, "ages": [20]}, format="json").data
    assert next(r for r in low["results"] if r["code"] == "premio_anual")["value"] == "1000.00"


@pytest.mark.django_db
def test_the_product_formulas_price_the_quote(admin_client, approver):  # noqa: F811
    scope = _priced_scope(admin_client, approver, "SETUP-QUOTE")
    quote_id = scope["quote"]["id"]
    technical = admin_client.post(f"/api/v1/quotes/{quote_id}/price").data
    assert technical["totalAmount"].startswith("100000")

    _publish_setup(admin_client, approver, scope["productId"])
    assert _select(admin_client, quote_id, {"productOptions": {"actividade": ["nao_existe"]}}).status_code == 400
    # Formulário a meio: a escolha fica gravada, com aviso; o cálculo pede o que falta.
    partial = _select(admin_client, quote_id, {"productOptions": {"actividade": "construcao"}})
    assert partial.status_code == 200, partial.data
    assert partial.data["selection"]["productOptions"] == {"actividade": ["construcao"]}
    assert [w["code"] for w in partial.data["warnings"]] == ["PRODUCT_INPUT_INCOMPLETE"]
    missing = admin_client.post(f"/api/v1/quotes/{quote_id}/price")
    assert missing.status_code == 422 and "Massa Salarial" in str(missing.data)

    chosen = _select(admin_client, quote_id, {"productOptions": {"actividade": "construcao", "multiplicador": ["base", "extra"]},
                                              "productFields": {"massa_salarial": "1000000"}})
    assert chosen.status_code == 200, chosen.data
    priced = admin_client.post(f"/api/v1/quotes/{quote_id}/price")
    assert priced.status_code == 200, priced.data
    # 100 000 (prémio técnico) + 0,05 × 1 000 000 × 1,5 + 300 (idade 46 → faixa 40+)
    assert Decimal(priced.data["totalAmount"]) == Decimal("175300.00")
    components = {c["code"]: c for c in priced.data["components"]}
    assert "PRODUCT_FORMULA:premio_anual" in components and "PRODUCT_FORMULAS" in components
    assert priced.data["versions"]["businessConfigurationVersions"][f"product.pricing_setup:{scope['productId']}"]["versionNo"] == 1

    # Fracionamento: a prestação semestral é a da fórmula do produto.
    draft = admin_client.get(f"/api/v1/quotes/{quote_id}/policy-draft").data
    semestral = draft["installmentsPreview"]["SEMESTRAL"]
    assert Decimal(str(semestral[0]["amount"])) == Decimal("87650.00")


@pytest.mark.django_db
def test_a_formula_outside_its_scope_does_not_apply(admin_client, approver):  # noqa: F811
    scope = _priced_scope(admin_client, approver, "SETUP-SCOPE")
    group_only = json.loads(json.dumps(SETUP))
    for formula in group_only["formulas"]:
        formula["scope"] = {"policyTypes": ["GROUP"]}
    _publish_setup(admin_client, approver, scope["productId"], group_only)
    priced = admin_client.post(f"/api/v1/quotes/{scope['quote']['id']}/price", {"recalculate": True}, format="json")
    assert priced.status_code == 200, priced.data
    assert priced.data["totalAmount"].startswith("100000")  # cotação individual: só o prémio técnico
    assert not any(c["code"].startswith("PRODUCT_FORMULA") for c in priced.data["components"])
