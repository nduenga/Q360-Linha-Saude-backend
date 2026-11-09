"""Comparador de planos: `GET /plans/compare` sobre os planos do PDF
"Coberturas e Capitais" carregados pelos modelos de mercado."""
from __future__ import annotations

import uuid

import pytest

from tests.product.conftest import make_client

URL = "/api/v1/plans/compare"


@pytest.fixture
def market_plans(admin_client):
    admin_client.post("/api/v1/product-templates/market", {}, format="json")
    return {p["code"]: p for p in admin_client.get("/api/v1/plans?size=50").data["items"]}


def _compare(client, *plans, **params):
    query = ",".join(p["id"] for p in plans)
    extra = "".join(f"&{k}={v}" for k, v in params.items())
    return client.get(f"{URL}?planIds={query}{extra}")


def _section(data, key):
    return next(s for s in data["sections"] if s["key"] == key)


def _row(section, key):
    return next(r for r in section["rows"] if r["key"] == key)


@pytest.mark.django_db
def test_compare_individual_plans_side_by_side(admin_client, market_plans):
    base, superior = market_plans["IND-BASE"], market_plans["IND-SUPERIOR"]
    response = _compare(admin_client, base, superior)
    assert response.status_code == 200, response.data
    data = response.data

    assert [p["planCode"] for p in data["plans"]] == ["IND-BASE", "IND-SUPERIOR"]
    assert data["pricing"]["available"] is False
    assert not any(w["code"] == "SEGMENT_MISMATCH" for w in data["warnings"])

    # Capitais: um valor por plano, com forma de garantia e moeda
    capitals = _section(data, "capitals")
    hospital = _row(capitals, "HOSPITALIZATION")
    assert all(c["state"] == "VALUE" for c in hospital["cells"])
    assert hospital["cells"][0]["value"]["kind"] == "ANNUAL_PER_PERSON"
    assert hospital["cells"][0]["currency"] == "AOA"
    assert hospital["different"] is True

    # Secção própria da cobertura com inclusão e capital principal
    coverage = _section(data, "coverage.HOSPITALIZATION")
    assert coverage["kind"] == "COVERAGE" and coverage["coverageCategory"] == "BASE"
    assert [c["value"] for c in _row(coverage, "inclusion")["cells"]] == ["INCLUDED", "INCLUDED"]

    # Elegibilidade: regras de grupo não se aplicam a planos individuais
    eligibility = _section(data, "eligibility")
    assert {c["state"] for c in _row(eligibility, "groupAdhesion")["cells"]} == {"NOT_APPLICABLE"}

    # Resumo factual: o capital de hospitalização mais alto pertence ao Superior
    higher = next(f for f in data["summary"] if f["type"] == "CAPITAL_HIGHER" and f["coverageCode"] == "HOSPITALIZATION")
    assert higher["planIds"] == [superior["id"]]
    assert higher["currency"] == "AOA"


@pytest.mark.django_db
def test_coverage_missing_in_a_plan_is_not_included(admin_client, market_plans):
    base, superior = market_plans["IND-BASE"], market_plans["IND-SUPERIOR"]
    data = _compare(admin_client, base, superior).data
    base_codes = {r["benefit"]["code"] for r in admin_client.get(f"/api/v1/plans/{base['id']}/benefits").data}
    superior_codes = {r["benefit"]["code"] for r in admin_client.get(f"/api/v1/plans/{superior['id']}/benefits").data}
    only_superior = sorted(superior_codes - base_codes)
    if not only_superior:
        pytest.skip("Os modelos de mercado têm as mesmas coberturas nos dois planos")
    code = only_superior[0]
    inclusion = _row(_section(data, f"coverage.{code}"), "inclusion")
    assert inclusion["cells"][0] == {"state": "NOT_INCLUDED", "value": None}
    assert inclusion["cells"][1]["state"] == "VALUE"
    fact = next(f for f in data["summary"] if f["type"] == "COVERAGE_NOT_IN_ALL" and f["coverageCode"] == code)
    assert fact["planIds"] == [superior["id"]]


@pytest.mark.django_db
def test_only_differences_hides_equal_rows(admin_client, market_plans):
    data = _compare(admin_client, market_plans["IND-BASE"], market_plans["IND-MEDIO"], onlyDifferences="true").data
    assert data["onlyDifferences"] is True
    assert data["sections"]
    assert all(r["different"] for s in data["sections"] for r in s["rows"])
    identification = next((s for s in data["sections"] if s["key"] == "identification"), None)
    assert identification is None or not any(r["key"] == "segment" for r in identification["rows"])


@pytest.mark.django_db
def test_individual_vs_group_warns(admin_client, market_plans):
    data = _compare(admin_client, market_plans["IND-MEDIO"], market_plans["GRP-COLABORADORES"]).data
    assert any(w["code"] == "SEGMENT_MISMATCH" for w in data["warnings"])
    eligibility = _section(data, "eligibility")
    spouse = _row(eligibility, "spouse")["cells"]
    assert spouse[1]["state"] == "NOT_APPLICABLE"


@pytest.mark.django_db
def test_inactive_plan_is_flagged(admin_client, market_plans):
    base = market_plans["IND-BASE"]
    detail = admin_client.get(f"/api/v1/plans/{base['id']}").data
    from apps.product.infrastructure.models import Plan

    Plan.all_tenants.filter(id=detail["id"]).update(status="INACTIVE")
    data = _compare(admin_client, base, market_plans["IND-MEDIO"]).data
    assert any(w["code"] == "PLAN_INACTIVE" and w["planId"] == base["id"] for w in data["warnings"])


@pytest.mark.django_db
@pytest.mark.parametrize("ids", ["", "not-a-uuid,{a}", "{a}", "{a},{a}"])
def test_invalid_plan_ids_are_rejected(admin_client, market_plans, ids):
    a = market_plans["IND-BASE"]["id"]
    response = admin_client.get(f"{URL}?planIds={ids.format(a=a)}")
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_too_many_plans_rejected(admin_client, market_plans):
    plans = list(market_plans.values())[:5]
    assert _compare(admin_client, *plans).status_code == 400


@pytest.mark.django_db
def test_unknown_plan_is_not_found(admin_client, market_plans):
    response = admin_client.get(f"{URL}?planIds={market_plans['IND-BASE']['id']},{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.django_db
def test_other_tenant_plans_are_not_visible(admin_client, market_plans):
    from apps.foundation.infrastructure.models import Tenant

    other = Tenant.objects.create(id=uuid.uuid4(), code=f"other-{uuid.uuid4().hex[:6]}", name="Outro")
    client = make_client(tenant_id=other.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin")
    response = _compare(client, market_plans["IND-BASE"], market_plans["IND-MEDIO"])
    assert response.status_code == 404


@pytest.mark.django_db
def test_read_scope_is_enough(tenant, admin_client, market_plans):
    reader = make_client(tenant_id=tenant.id, roles=["SUBSCRIBER"], scope="q360.read")
    assert _compare(reader, market_plans["IND-BASE"], market_plans["IND-MEDIO"]).status_code == 200
