"""Modelo actuarial configurável pela interface (decisões de 2026-10-14):
importação de Excel (A1), validação ao gravar, valores por omissão do perfil
(A4), idade de adesão em renovações (A6), fracionamento para todas as apólices
(A8) e fórmulas por pessoa num cálculo real (A9)."""
from __future__ import annotations

import copy
import json
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.business_config.domain.actuarial_model import RECOMMENDED_CALCULATION_SETTINGS
from apps.business_config.seed.actuarial_model import WORKBOOK_PATH, build_actuarial_model
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId
from apps.policy.application.issuance_service import installment_amount
from apps.pricing.application.pricing_engine import _entry_age_for
from apps.quote.infrastructure.models import Quote
from tests.quote.conftest import make_client
from tests.quote.test_business_config_e2e import BASE, SCOPE, _publish, _values
from tests.quote.test_formula_config_e2e import _priced_quote

ACTUARIAL = "/api/v1/business-config/actuarial-model"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def approver(tenant):
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPE, actor_id="approver-1")


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _workbook(name="modelo.xlsx", content=None):
    return SimpleUploadedFile(name, content if content is not None else WORKBOOK_PATH.read_bytes(), content_type=XLSX)


# --- A1: importação, modelo de referência, catálogo e validação ---------------

@pytest.mark.django_db
def test_import_excel_creates_a_draft_for_approval_with_the_file_attached(admin_client, approver):
    preview = admin_client.post(f"{ACTUARIAL}/import", {"file": _workbook(), "effectiveFrom": "2026-01-01",
                                                        "dryRun": True}, format="multipart")
    assert preview.status_code == 200, preview.data
    assert preview.data["summary"]["purePremiumRows"] == 94
    assert admin_client.get(BASE, {"configKey": "pricing.actuarial_model"}).data["items"] == []  # nada gravado

    created = admin_client.post(f"{ACTUARIAL}/import", {"file": _workbook(), "effectiveFrom": "2026-01-01"},
                                format="multipart")
    assert created.status_code == 201, created.data
    assert created.data["status"] == "DRAFT"
    assert created.data["metadata"]["source"] == "EXCEL_IMPORT" and len(created.data["metadata"]["sha256"]) == 64
    assert created.data["value"]["calculation_settings"] == RECOMMENDED_CALCULATION_SETTINGS
    documents = admin_client.get(f"{BASE}/{created.data['id']}/documents").data["items"]
    assert [d["documentType"] for d in documents] == ["ACTUARIAL_WORKBOOK"]

    # o ciclo normal: outro utilizador aprova; uma nova importação mantém as opções ajustadas na interface
    value = copy.deepcopy(created.data["value"])
    value["calculation_settings"]["entry_age_on_renewal"] = "CURRENT_AGE"
    edited = admin_client.put(f"{BASE}/{created.data['id']}", {"value": value, "rowVersion": created.data["rowVersion"]},
                              format="json")
    assert edited.status_code == 200, edited.data
    assert admin_client.post(f"{BASE}/{created.data['id']}", {"action": "submit"}, format="json").status_code == 200
    assert approver.post(f"{BASE}/{created.data['id']}/approve").data["status"] == "PUBLISHED"
    again = admin_client.post(f"{ACTUARIAL}/import", {"file": _workbook(), "effectiveFrom": "2026-02-01"},
                              format="multipart")
    assert again.status_code == 201, again.data
    assert "calculation_settings" in again.data["keptFromPublished"]
    assert again.data["value"]["calculation_settings"]["entry_age_on_renewal"] == "CURRENT_AGE"


@pytest.mark.django_db
def test_import_rejects_files_that_are_not_the_model(admin_client):
    not_excel = admin_client.post(f"{ACTUARIAL}/import", {"file": _workbook(content=b"isto nao e um excel"),
                                                          "effectiveFrom": "2026-01-01"}, format="multipart")
    assert not_excel.status_code == 400 and "Excel" in not_excel.data["detail"]
    wrong_type = admin_client.post(f"{ACTUARIAL}/import", {"file": _workbook(name="modelo.csv"),
                                                           "effectiveFrom": "2026-01-01"}, format="multipart")
    assert wrong_type.status_code == 400


@pytest.mark.django_db
def test_invalid_model_edits_are_rejected_when_saving(admin_client):
    model = build_actuarial_model()
    model["assumptions"]["loadings"]["SAU"]["insurer_margin"] = 0.9  # encargos + margem >= 100 %
    bad = admin_client.post(BASE, {"configKey": "pricing.actuarial_model", "value": model, "effectiveFrom": "2026-01-01"},
                            format="json")
    assert bad.status_code == 400 and "assumptions.loadings.SAU" in bad.data["detail"]
    model = build_actuarial_model()
    model["calculation_settings"]["profile_defaults"]["SAU"]["region"] = "Marte"
    bad = admin_client.post(BASE, {"configKey": "pricing.actuarial_model", "value": model, "effectiveFrom": "2026-01-01"},
                            format="json")
    assert bad.status_code == 400 and "Marte" in bad.data["detail"]


@pytest.mark.django_db
def test_template_and_catalog(admin_client):
    template = admin_client.get(f"{ACTUARIAL}/template")
    assert template.status_code == 200
    assert b"".join(template.streaming_content)[:2] == b"PK"
    catalog = admin_client.get(f"{ACTUARIAL}/catalog").data
    assert {o["value"] for o in catalog["calculationSettings"]["entryAgeOnRenewal"]} == {
        "ORIGINAL_ENTRY_AGE", "CURRENT_AGE", "NOT_APPLIED"}
    assert "calculation_settings" in {s["key"] for s in catalog["sections"]}


# --- A4: perfil actuarial por omissão --------------------------------------

def _market_quote(client, approver, plan_code, proposer, model):
    assert client.post("/api/v1/product-templates/market", {}, format="json").status_code == 200
    plan = {p["code"]: p for p in client.get("/api/v1/plans?size=50").data["items"]}[plan_code]
    for key, value in _values("1").items():
        _publish(client, approver, key, value)
    _publish(client, approver, "pricing.actuarial_model", model)
    rule = client.post("/api/v1/rule-versions", {"code": "ELIG-DEF", "name": "E", "ruleDomain": "ELIGIBILITY",
                                                 "effectiveFrom": "2026-01-01", "artifactType": "JSON",
                                                 "artifactRef": json.dumps({})}, format="json").data
    client.post(f"/api/v1/configuration/rule-version/{rule['id']}/publish")
    created = client.post("/api/v1/proposers", proposer, format="json")
    assert created.status_code == 201, created.data
    quote = client.post("/api/v1/quotes", {"proposerId": created.data["id"], "planId": plan["id"]},
                        format="json").data
    member = client.post("/api/v1/members", {"firstName": "Pessoa", "proposerId": created.data["id"], "relationshipCode": "TITULAR",
                                             "sexCode": "M", "dateOfBirth": "1960-01-15"}, format="json")
    assert member.status_code == 201, member.data
    client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member.data["id"]}, format="json")
    return quote


GROUP = {"proposerType": "ORGANISATION", "displayName": "Empresa sem perfil", "registrationNumber": "5417000002",
         "email": "rh@example.com", "phone": "+244900000000"}
# Só a dimensão do grupo (a tabela começa nos 5 colaboradores; abaixo disso é SAU).
GROUP_WITH_HEADCOUNT = {**GROUP, "attributes": {"actuarialProfile": {"groupHeadcount": 40}}}


@pytest.mark.django_db
def test_group_without_profile_uses_the_configured_defaults(admin_client, approver):
    quote = _market_quote(admin_client, approver, "GRP-QUADROS", GROUP_WITH_HEADCOUNT, build_actuarial_model())
    priced = admin_client.post(f"/api/v1/quotes/{quote['id']}/price", {"recalculate": True}, format="json")
    assert priced.status_code == 200, priced.data
    steps = admin_client.get(f"/api/v1/pricing/{priced.data['pricingRunId']}/explanation").data["steps"]
    resolved = next(s for s in steps if s["stepCode"] == "ACTUARIAL_PROFILE_RESOLVED")
    # A adesão vem da regra do plano (obrigatória/facultativa), não das predefinições.
    assert resolved["output"]["defaultsApplied"] == [
        "costSharing", "crossSell", "industry", "noClaimsRenewal", "region"]
    assert resolved["output"]["profile"]["adhesion"] in ("MANDATORY", "VOLUNTARY")
    assert resolved["output"]["profile"]["groupHeadcount"] == 40  # o que o tomador indicou prevalece
    assert resolved["output"]["profile"]["industry"] == "Comércio e Serviços"


@pytest.mark.django_db
def test_model_without_settings_keeps_the_strict_behaviour(admin_client, approver):
    model = build_actuarial_model()
    del model["calculation_settings"]
    quote = _market_quote(admin_client, approver, "GRP-QUADROS", GROUP_WITH_HEADCOUNT, model)
    priced = admin_client.post(f"/api/v1/quotes/{quote['id']}/price", {"recalculate": True}, format="json")
    assert priced.status_code == 422, priced.data
    # Mensagem para quem usa o ecrã: nomes de negócio, não os campos técnicos.
    assert "sector de atividade" in priced.data["detail"] and "região" in priced.data["detail"]


# --- A6: idade de adesão em renovações -------------------------------------

def test_entry_age_rule_for_renewals():
    member = {"age": 67, "entryAge": 52}
    assert _entry_age_for(context={}, member_context=member, mode="NOT_APPLIED") == (67, None)  # adesão nova
    renewal = {"quoteType": "RENEWAL"}
    assert _entry_age_for(context=renewal, member_context=member, mode="ORIGINAL_ENTRY_AGE") == (52, None)
    assert _entry_age_for(context=renewal, member_context={"age": 67}, mode="ORIGINAL_ENTRY_AGE") == (
        None, "ENTRY_AGE_UNKNOWN")
    assert _entry_age_for(context=renewal, member_context=member, mode="CURRENT_AGE") == (67, None)
    assert _entry_age_for(context=renewal, member_context=member, mode="NOT_APPLIED") == (None, "RENEWAL")


# --- A8 e A9: fracionamento e fórmulas por pessoa sem modelo actuarial -----

@pytest.mark.django_db
def test_fractionation_applies_without_actuarial_model(admin_client, approver, tenant):
    quote, priced = _priced_quote(admin_client, approver)
    total = Decimal(priced["totalAmount"])

    def installment(frequency):
        token = CurrentActorProvider.bind(Actor(actor_id="test", tenant_id=TenantId(tenant.id), roles=frozenset()))
        try:
            row = Quote.objects.select_related("latest_pricing_run").get(id=quote["id"])
            return installment_amount(row, total, frequency)
        finally:
            CurrentActorProvider.reset(token)

    assert installment("MENSAL") == (total / 12).quantize(Decimal("0.01"))  # sem tabela: partes iguais
    _publish(admin_client, approver, "pricing.fractionation",
             {"installments": [{"frequency": "ANUAL", "loading": "0"}, {"frequency": "MENSAL", "loading": "0.04"}]})
    assert installment("MENSAL") == (total * Decimal("1.04") / 12).quantize(Decimal("0.01"))
    assert installment("ANUAL") == total
    duplicated = admin_client.post(BASE, {"configKey": "pricing.fractionation", "effectiveFrom": "2026-01-01",
                                          "value": {"installments": [{"frequency": "MENSAL", "loading": "0.04"},
                                                                     {"frequency": "MENSAL", "loading": "0.05"}]}},
                                   format="json")
    assert duplicated.status_code == 400


@pytest.mark.django_db
def test_person_formulas_change_each_member_premium(admin_client, approver):
    quote, before = _priced_quote(admin_client, approver)
    assert before["totalAmount"] == "100000.00"
    _publish(admin_client, approver, "pricing.formulas", {"rules": [
        {"code": "carga_pessoa", "name": "Carga por pessoa", "stage": "PERSON",
         "expression": "person_amount * 1.1 + members_count * 0"},
    ]})
    after = admin_client.post(f"/api/v1/quotes/{quote['id']}/price")
    assert after.status_code == 200, after.data
    assert after.data["totalAmount"] == "110000.00"
    component = next(c for c in after.data["components"] if c["code"] == "carga_pessoa")
    assert component["memberId"] is not None and component["adjustmentAmount"] == "10000.00"
    steps = admin_client.get(f"/api/v1/pricing/{after.data['pricingRunId']}/explanation").data["steps"]
    applied = next(s for s in steps if s["stepCode"] == "FORMULA_APPLIED")
    assert applied["input"]["stage"] == "PERSON" and applied["input"]["memberId"] == component["memberId"]


@pytest.mark.django_db
def test_import_for_one_product_creates_the_product_version(admin_client):
    """Com `productId`, a importação cria `pricing.actuarial_model@<produto>`
    (substitui a geral nesse produto) e não mexe na versão geral."""
    product = admin_client.post("/api/v1/products", {"code": "ACT-PROD", "name": "Produto atuarial"}).data
    preview = admin_client.post(f"{ACTUARIAL}/import", {"file": _workbook(), "effectiveFrom": "2026-01-01",
                                                         "dryRun": "true", "productId": product["id"]}, format="multipart")
    assert preview.status_code == 200, preview.data
    created = admin_client.post(f"{ACTUARIAL}/import", {"file": _workbook(), "effectiveFrom": "2026-01-01",
                                                         "productId": product["id"]}, format="multipart")
    assert created.status_code == 201, created.data
    assert created.data["configKey"] == f"pricing.actuarial_model@{product['id']}" and created.data["status"] == "DRAFT"
    general = admin_client.get("/api/v1/business-config/configurations", {"configKey": "pricing.actuarial_model"}).data
    assert all(item["configKey"] == "pricing.actuarial_model" for item in general.get("items", general))
    unknown = admin_client.post(f"{ACTUARIAL}/import", {"file": _workbook(), "effectiveFrom": "2026-01-01",
                                                         "productId": "00000000-0000-0000-0000-000000000000"},
                                format="multipart")
    assert unknown.status_code == 400
