"""Conversão da tarifa antiga (tabela de tarifação + conjunto de parâmetros)
para a configuração de negócio: rascunhos que, depois de aprovados, dão o
mesmo prémio; o que não é convertível fica no relatório."""
from __future__ import annotations

import io
import json

import pytest
from django.core.management import call_command

from tests.quote.conftest import make_client
from tests.quote.test_business_config_e2e import BASE, SCOPE
from tests.quote.test_quotes import _member, _quote_scope
from tests.quote.test_review_workflow import _eligibility_rule


def _run(tenant, *args) -> dict:
    out = io.StringIO()
    call_command("migrate_legacy_tariffs", "--tenant-code", tenant.code, *args, stdout=out)
    return json.loads(out.getvalue())


@pytest.mark.django_db
def test_legacy_tariff_converts_to_drafts_that_keep_the_premium(admin_client, tenant):
    approver = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPE, actor_id="approver-1")
    scope = _quote_scope(admin_client, code_suffix="MIG")
    _eligibility_rule(admin_client, code="ELIG-MIG")
    quote = admin_client.post("/api/v1/quotes", {"proposerId": scope["proposerId"], "planId": scope["planId"]},
                              format="json").data
    member_id = _member(admin_client, proposer_id=scope["proposerId"])
    admin_client.post(f"/api/v1/quotes/{quote['id']}/members", {"memberId": member_id}, format="json")
    legacy = admin_client.post(f"/api/v1/quotes/{quote['id']}/price", {"recalculate": True}, format="json")
    assert legacy.status_code == 200, legacy.data

    dry = _run(tenant, "--dry-run")
    assert dry["dryRun"] is True and {c["configKey"] for c in dry["created"]} == {"pricing.reference_premiums", "pricing.factors"}
    assert admin_client.get(BASE, {"configKey": "pricing.factors"}).data["items"] == []

    report = _run(tenant, "--effective-from", "2026-01-01")
    created = {c["configKey"]: c for c in report["created"]}
    assert all(c["status"] == "DRAFT" for c in created.values())
    assert created["pricing.factors"]["value"]["factors"] == [
        {"code": "AGE_FACTOR", "dimension": "planCode", "condition": "*", "factor": "1"}]

    for item in created.values():
        cid = item["configurationId"]
        assert admin_client.post(f"{BASE}/{cid}", {"action": "submit"}, format="json").status_code == 200
        assert approver.post(f"{BASE}/{cid}/approve").status_code == 200
    # Faltam as restantes chaves da tarifa nova para o motor a usar.
    for key, value in (("pricing.adjustments", {"rules": []}), ("pricing.taxes_fees", {"charges": []})):
        cid = admin_client.post(BASE, {"configKey": key, "value": value, "effectiveFrom": "2026-01-01"},
                                format="json").data["id"]
        admin_client.post(f"{BASE}/{cid}", {"action": "submit"}, format="json")
        approver.post(f"{BASE}/{cid}/approve")

    migrated = admin_client.post(f"/api/v1/quotes/{quote['id']}/price", {"recalculate": True}, format="json")
    assert migrated.status_code == 200, migrated.data
    assert migrated.data["totalAmount"] == legacy.data["totalAmount"]
    assert "pricing.reference_premiums" in migrated.data["versions"]["businessConfigurationVersions"]


@pytest.mark.django_db
def test_factors_that_cannot_be_converted_are_reported(admin_client, tenant):
    created = admin_client.post("/api/v1/rating-tables", {
        "code": "MIX", "name": "MIX", "effectiveFrom": "2026-01-01", "currencyCode": "AOA",
        "factors": [
            {"factorCode": "REGION", "dimensions": {}, "factorValue": "1.00"},
            {"factorCode": "REGION", "dimensions": {"region": "LUANDA"}, "factorValue": "1.10", "priority": 1},
            {"factorCode": "COMBO", "dimensions": {"region": "LUANDA", "segment": "GROUP"}, "factorValue": "0.9"},
            {"factorCode": "SEGMENT", "dimensions": {"segment": "GROUP"}, "factorValue": "0.95"},
        ],
    }, format="json").data
    admin_client.post(f"/api/v1/configuration/rating-table/{created['id']}/publish")
    report = _run(tenant, "--dry-run")
    reasons = {s["factorCode"]: s["reason"] for s in report["skipped"] if s.get("factorCode")}
    assert set(reasons) == {"REGION", "COMBO"}
    factors = next(c for c in report["created"] if c["configKey"] == "pricing.factors")["value"]["factors"]
    assert factors == [{"code": "SEGMENT", "dimension": "segment", "condition": "GROUP", "factor": "0.95"}]
