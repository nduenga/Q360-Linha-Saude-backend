"""A gama Protteja carregada pelo seed reproduz os prémios das propostas de exemplo."""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.business_config.infrastructure.models import BusinessConfiguration
from apps.product.infrastructure.models import Plan
from apps.product.seed import protteja_saude as data
from apps.staff_accounts.infrastructure.models import StaffAccount, StaffAccountRole
from tests.policy.conftest import make_client
from tests.policy.test_issuance import _eligibility_rule

SCOPE = "q360.read q360.write q360.admin q360.approve"


def _approver(tenant) -> StaffAccount:
    account = StaffAccount.all_tenants.create(
        tenant_id=tenant.id, email="aprovador@demo.q360.local", name="Aprovadora", password_hash="x"
    )
    StaffAccountRole.all_tenants.create(tenant_id=tenant.id, staff_account=account, role="ADMIN")
    return account


def _born(age: int) -> str:
    today = datetime.date.today()
    return (today.replace(year=today.year - age) - datetime.timedelta(days=40)).isoformat()


def _seed(tenant, **extra):
    call_command("seed_protteja_products", tenant_code=tenant.code, **extra)


@pytest.mark.django_db
def test_production_run_leaves_everything_waiting_for_approval(admin_client, tenant):
    _seed(tenant)
    plans = Plan.all_tenants.filter(tenant_id=tenant.id, code__startswith="PROTTEJA-")
    assert plans.count() == 8
    assert set(plans.values_list("status", flat=True)) == {"INACTIVE"}
    configs = BusinessConfiguration.all_tenants.filter(tenant_id=tenant.id, config_key__contains="@")
    assert configs.count() == 10
    assert set(configs.values_list("status", flat=True)) == {"PENDING_APPROVAL"}

    _seed(tenant)  # repetir não duplica nada
    assert BusinessConfiguration.all_tenants.filter(tenant_id=tenant.id, config_key__contains="@").count() == 10
    assert Plan.all_tenants.filter(tenant_id=tenant.id, code__startswith="PROTTEJA-").count() == 8


@pytest.mark.django_db
@pytest.mark.parametrize("level", ["BUS", "BPL", "PRE", "PPL"])
def test_family_premium_matches_the_example_proposal(admin_client, tenant, level):
    _eligibility_rule(admin_client, code=f"PROTTEJA-ELIG-{level}", config={})
    approver = _approver(tenant)
    _seed(tenant, approve_as=approver.email)
    plan = Plan.all_tenants.get(tenant_id=tenant.id, code=data.plan_code(level, False))
    assert plan.status == "ACTIVE"

    proposer = admin_client.post("/api/v1/proposers", {
        "proposerType": "INDIVIDUAL", "dateOfBirth": _born(38), "displayName": "João Exemplo",
        "registrationNumber": "000000123LA042", "email": "joao@demo.q360.local", "phone": "+244900000000",
    }).data
    people = [("TITULAR", "João", 38), ("CONJUGE", "Maria", 35), ("FILHO", "Ana", 12), ("FILHO", "Pedro", 8)]
    quote = admin_client.post("/api/v1/quotes", {"planId": str(plan.id), "proposerId": proposer["id"]}, format="json").data
    for relationship, name, age in people:
        member = admin_client.post("/api/v1/members", {
            "firstName": name, "lastName": "Exemplo", "proposerId": proposer["id"],
            "relationshipCode": relationship, "dateOfBirth": _born(age),
        }).data
        added = admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member["id"]}, format="json")
        assert added.status_code in (200, 201), added.data
    priced = admin_client.post(f"/api/v1/quotes/{quote['id']}/price")
    assert priced.status_code in (200, 201), priced.data
    assert Decimal(priced.data["totalAmount"]) == data.INDIVIDUAL_EXAMPLE_TOTALS[level]


@pytest.mark.django_db
def test_fractionation_and_group_rules_are_published_per_product(admin_client, tenant):
    from apps.foundation.application.context import CurrentActorProvider
    from apps.policy.application.issuance_service import _loading_for

    approver = _approver(tenant)
    _seed(tenant, approve_as=approver.email)
    group_product = Plan.all_tenants.get(tenant_id=tenant.id, code=data.plan_code("BUS", True)).product_id
    published = {
        c.config_key.split("@")[0]: c.value_json
        for c in BusinessConfiguration.all_tenants.filter(
            tenant_id=tenant.id, config_key__endswith=f"@{group_product}", status="PUBLISHED"
        )
    }
    loadings = {f: _loading_for(published["pricing.fractionation"]["installments"], f) for f in data.FRACTIONATION}
    assert loadings == {"ANUAL": Decimal("0"), "SEMESTRAL": Decimal("0.03"), "TRIMESTRAL": Decimal("0.05"), "MENSAL": Decimal("0.07")}
    rule = published["rules.custom"]["rules"][0]
    assert (rule["field"], rule["operator"], rule["value"], rule["amount"]) == ("members_count", "GT", "100", "12")
    adults = [r for r in published["pricing.reference_premiums"]["premiums"]
              if r["plan"] == data.plan_code("BUS", True) and r["age_from"] == 18]
    assert adults[0]["annual_premium"] == "247500"
    del CurrentActorProvider


@pytest.mark.django_db
def test_proposal_template_fills_every_marker(admin_client, tenant):
    from apps.quote.application import template_files, word_template
    from apps.quote.infrastructure.models import DocumentTemplateVersion

    approver = _approver(tenant)
    _seed(tenant, approve_as=approver.email)
    template = DocumentTemplateVersion.all_tenants.get(tenant_id=tenant.id, template_code="PROTTEJA-PROPOSTA-SAUDE")
    assert template.status == "PUBLISHED"
    data = template_files.read_word(template)
    scalars = {name: f"<{name}>" for name in word_template.allowed_names("QUOTE_PROPOSAL") if "." in name}
    groups = {
        "coverage": [{"name": "Hospitalização", "limits": "5.000.000 Kz", "participation": "Isento",
                      "waiting": "30 dias", "priorApproval": "Não"},
                     {"name": "Ambulatório", "limits": "750.000 Kz", "participation": "2.500 Kz",
                      "waiting": "30 dias", "priorApproval": "Não"}],
        "insured": [{"name": "Ana", "relationship": "Titular", "age": "38", "status": "Incluída"},
                    {"name": "Rui", "relationship": "Cônjuge", "age": "35", "status": "Incluída"}],
    }
    filled = word_template.fill(data, scalars=scalars, groups=groups)
    assert word_template.placeholders_in(filled) == set()
    import io

    from docx import Document

    document = Document(io.BytesIO(filled))
    text = "\n".join(p.text for c in word_template._containers(document) for p in word_template._iter_paragraphs(c))  # noqa: SLF001
    assert "Ana" in text and "Rui" in text and "<client.name>" in text
    assert "João Exemplo" not in text and "Documento de exemplo" not in text and "745.500" not in text


# ------------------------------------------------- tarifa por relação
class _Pricing:
    def __init__(self, rows):
        self.reference_premiums = {"currency_code": "AOA", "premiums": rows}


class _Plan:
    code = "P1"
    name = "Plano 1"


def test_a_relationship_row_wins_over_the_age_only_row():
    from apps.business_config.application.pricing import resolve_reference_premium

    pricing = _Pricing([
        {"plan": "P1", "age_from": 0, "age_to": 17, "annual_premium": "100"},
        {"plan": "P1", "age_from": 18, "age_to": 65, "annual_premium": "300"},
        {"plan": "P1", "age_from": 0, "age_to": 24, "relationship": "CHILD", "annual_premium": "100"},
    ])
    assert resolve_reference_premium(pricing=pricing, plan=_Plan, age=20, relationship="CHILD") == Decimal("100")
    assert resolve_reference_premium(pricing=pricing, plan=_Plan, age=20, relationship="SPOUSE") == Decimal("300")
    assert resolve_reference_premium(pricing=pricing, plan=_Plan, age=20) == Decimal("300")
    assert resolve_reference_premium(pricing=pricing, plan=_Plan, age=10, relationship="CHILD") == Decimal("100")
    assert resolve_reference_premium(pricing=pricing, plan=_Plan, age=40, relationship="COLLABORATOR") == Decimal("300")


def test_a_titular_row_also_prices_the_company_collaborator():
    from apps.business_config.application.pricing import resolve_reference_premium

    pricing = _Pricing([
        {"plan": "P1", "age_from": 18, "age_to": 65, "annual_premium": "300"},
        {"plan": "P1", "age_from": 18, "age_to": 65, "relationship": "TITULAR", "annual_premium": "350"},
    ])
    assert resolve_reference_premium(pricing=pricing, plan=_Plan, age=40, relationship="COLLABORATOR") == Decimal("350")
    assert resolve_reference_premium(pricing=pricing, plan=_Plan, age=40, relationship="SPOUSE") == Decimal("300")


def test_an_unknown_relationship_is_refused():
    from apps.business_config.domain.errors import InvalidConfiguration
    from apps.business_config.domain.validators import validate_for_publication as validate

    value = {"currency_code": "AOA", "premiums": [
        {"plan": "P1", "age_from": 0, "age_to": 24, "relationship": "AVO", "annual_premium": "100"}]}
    with pytest.raises(InvalidConfiguration):
        validate("pricing.reference_premiums", value)


@pytest.mark.django_db
def test_student_child_of_20_pays_the_child_premium(admin_client, tenant):
    """Prémio por relação no motor real: um filho de 20 anos paga como filho
    quando a tarifa tem a linha «filho 0–24»."""
    _eligibility_rule(admin_client, code="PROTTEJA-ELIG-CHILD", config={})
    approver = _approver(tenant)
    _seed(tenant, approve_as=approver.email)
    plan = Plan.all_tenants.get(tenant_id=tenant.id, code=data.plan_code("BUS", False))
    published = BusinessConfiguration.all_tenants.get(
        tenant_id=tenant.id, config_key=f"pricing.reference_premiums@{plan.product_id}", status="PUBLISHED"
    )
    rows = published.value_json["premiums"] + [
        {"plan": plan.code, "age_from": 0, "age_to": 24, "relationship": "CHILD", "annual_premium": "145000"}]
    BusinessConfiguration.all_tenants.filter(id=published.id).update(value_json={**published.value_json, "premiums": rows})

    proposer = admin_client.post("/api/v1/proposers", {
        "proposerType": "INDIVIDUAL", "dateOfBirth": _born(45), "displayName": "Pai Exemplo",
        "registrationNumber": "000000124LA042", "email": "pai@demo.q360.local", "phone": "+244900000001",
    }).data
    quote = admin_client.post("/api/v1/quotes", {"planId": str(plan.id), "proposerId": proposer["id"]}, format="json").data
    for relationship, name, age in (("TITULAR", "Pai", 45), ("FILHO", "Estudante", 20)):
        member = admin_client.post("/api/v1/members", {
            "firstName": name, "lastName": "Exemplo", "proposerId": proposer["id"],
            "relationshipCode": relationship, "dateOfBirth": _born(age),
        }).data
        added = admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member["id"]}, format="json")
        assert added.status_code in (200, 201), added.data
    priced = admin_client.post(f"/api/v1/quotes/{quote['id']}/price")
    assert priced.status_code in (200, 201), priced.data
    assert Decimal(priced.data["totalAmount"]) == Decimal("285000") + Decimal("145000")


@pytest.mark.django_db
def test_general_form_lists_the_real_plans(admin_client, tenant):
    approver = _approver(tenant)
    _seed(tenant, approve_as=approver.email)
    catalog = admin_client.get("/api/v1/business-config/catalog")
    assert catalog.status_code == 200, catalog.data
    schema = next(i for i in catalog.data["items"] if i["key"] == "pricing.reference_premiums")["formSchema"]
    plan_field = next(f for s in schema["sections"] for f in s["fields"] if f["name"] == "plan")
    assert data.plan_code("PPL", True) in plan_field["options"]
    assert "Base" in plan_field["options"], "os nomes antigos continuam válidos"
    relationship = next(f for s in schema["sections"] for f in s["fields"] if f["name"] == "relationship")
    assert relationship["optionLabels"]["CHILD"] == "Filho"
