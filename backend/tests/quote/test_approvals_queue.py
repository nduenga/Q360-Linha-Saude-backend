"""Fila única de aprovações do tenant e área de cada tipo de configuração."""
from __future__ import annotations

import pytest

from tests.quote.conftest import make_client
from tests.quote.test_business_config_e2e import BASE, SCOPE, _publish, _values

QUEUE = "/api/v1/business-config/approvals/pending"


@pytest.mark.django_db
def test_queue_lists_pending_items_with_changes_and_who_can_approve(admin_client, tenant):
    approver = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPE, actor_id="approver-1")
    assert admin_client.get(QUEUE).data == {"total": 0, "byArea": {}, "items": []}

    _publish(admin_client, approver, "pricing.reference_premiums", _values("100000")["pricing.reference_premiums"])
    changed = admin_client.post(BASE, {"configKey": "pricing.reference_premiums",
                                       "value": _values("120000")["pricing.reference_premiums"],
                                       "effectiveFrom": "2026-12-01"}, format="json").data
    admin_client.post(f"{BASE}/{changed['id']}", {"action": "submit"}, format="json")
    new = admin_client.post(BASE, {"configKey": "rules.custom", "value": {"rules": []},
                                   "effectiveFrom": "2026-12-01"}, format="json").data
    admin_client.post(f"{BASE}/{new['id']}", {"action": "submit"}, format="json")
    # Um rascunho não submetido não entra na fila.
    admin_client.post(BASE, {"configKey": "pricing.factors", "value": {"factors": []}, "effectiveFrom": "2026-12-01"},
                      format="json")

    mine = admin_client.get(QUEUE).data
    assert mine["total"] == 2 and mine["byArea"] == {"TARIFF": 1, "RULES": 1}
    premiums = next(i for i in mine["items"] if i["configKey"] == "pricing.reference_premiums")
    assert premiums["againstVersionNo"] == 1 and premiums["changeCount"] == 1 and premiums["isNew"] is False
    assert premiums["changes"][0]["after"] == "120000" and premiums["label"] == "Prémios de referência"
    assert premiums["canApprove"] is False and "outra pessoa" in premiums["cannotApproveReason"]
    rules = next(i for i in mine["items"] if i["configKey"] == "rules.custom")
    assert rules["isNew"] is True and rules["area"] == "RULES"

    theirs = approver.get(QUEUE).data
    assert all(i["canApprove"] for i in theirs["items"])
    assert approver.get(f"{QUEUE}/count").data == {"total": 2, "canApprove": 2, "byArea": {"TARIFF": 1, "RULES": 1}}
    assert [i["configKey"] for i in admin_client.get(QUEUE, {"area": "RULES"}).data["items"]] == ["rules.custom"]
    assert admin_client.get(QUEUE, {"area": "XPTO"}).status_code == 400

    approver.post(f"{BASE}/{changed['id']}/approve")
    assert admin_client.get(f"{QUEUE}/count").data["total"] == 1


@pytest.mark.django_db
def test_every_configuration_type_has_an_area(admin_client):
    items = admin_client.get("/api/v1/business-config/catalog").data["items"]
    assert items and all(i["area"] in {"ORGANIZATION", "APPROVALS", "PRODUCTS", "TARIFF", "RULES", "PARAMETERS", "DOCUMENTS"} for i in items)
    by_key = {i["key"]: i["area"] for i in items}
    assert by_key["pricing.formulas"] == "TARIFF" and by_key["security.role_permissions"] == "ORGANIZATION"
    assert by_key["rules.custom"] == "RULES" and by_key["proposal.branding"] == "DOCUMENTS"
