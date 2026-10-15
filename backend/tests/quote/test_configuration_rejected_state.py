"""Decisão R2 (2026-10-14): a rejeição tem estado próprio (REJECTED, migração
da CHECK `ck_business_configuration_status`). Uma versão REJECTED não é
aprovável; o autor corrige-a (volta a DRAFT) ou reenvia-a."""
from __future__ import annotations

import pytest

from tests.quote.conftest import make_client
from tests.quote.test_business_config_e2e import BASE, SCOPE


@pytest.fixture
def approver(tenant):
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPE, actor_id="approver-1")


@pytest.mark.django_db
def test_rejected_is_a_state_of_its_own(admin_client, approver):
    created = admin_client.post(BASE, {"configKey": "renewal.deadlines", "value": {}, "effectiveFrom": "2026-01-01"},
                                format="json")
    assert created.status_code == 201, created.data
    cid = created.data["id"]
    assert admin_client.post(f"{BASE}/{cid}", {"action": "submit"}, format="json").data["status"] == "PENDING_APPROVAL"

    rejected = approver.post(f"{BASE}/{cid}/reject", {"reason": "Prazos por confirmar"}, format="json")
    assert rejected.status_code == 200, rejected.data
    assert rejected.data["status"] == "REJECTED"
    assert rejected.data["metadata"]["lastRejection"]["reason"] == "Prazos por confirmar"
    assert approver.post(f"{BASE}/{cid}/approve").status_code == 409  # só PENDING_APPROVAL é aprovável
    listed = admin_client.get(BASE, {"status": "REJECTED"}).data
    assert [c["id"] for c in listed["items"]] == [cid]

    # reenviar sem alterar; rejeitar outra vez; corrigir -> DRAFT
    assert admin_client.post(f"{BASE}/{cid}", {"action": "submit"}, format="json").data["status"] == "PENDING_APPROVAL"
    again = approver.post(f"{BASE}/{cid}/reject", {"reason": "Continua por confirmar"}, format="json").data
    assert again["status"] == "REJECTED" and len(again["metadata"]["rejections"]) == 2
    corrected = admin_client.put(f"{BASE}/{cid}", {"value": {}, "rowVersion": again["rowVersion"]}, format="json")
    assert corrected.status_code == 200, corrected.data
    assert corrected.data["status"] == "DRAFT"

    actions = [e["action"] for e in admin_client.get(f"{BASE}/{cid}/history").data["items"]]
    assert actions.count("BUSINESS_CONFIGURATION_REJECTED") == 2
