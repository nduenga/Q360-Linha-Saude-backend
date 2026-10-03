"""Renovação com configuração de negócio: prazos, inflação médica e fecho da
apólice de origem (RENEWED) só quando a renovação se converte em apólice."""
from __future__ import annotations

import datetime

import pytest

from tests.policy.conftest import make_client
from tests.policy.test_issuance import _SIGN_BODY, _approved_quote, _approver

BASE = "/api/v1/business-config/configurations"


def _publish(creator, approver, key, value):
    cid = creator.post(BASE, {"configKey": key, "value": value, "effectiveFrom": "2026-01-01"}, format="json").data["id"]
    creator.post(f"{BASE}/{cid}", {"action": "submit"}, format="json")
    assert approver.post(f"{BASE}/{cid}/approve").status_code == 200


def _issue_and_activate(tenant, quote, *, signed_at, paid_at):
    issued = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/policy",
        {**_SIGN_BODY, "signedAt": signed_at, "rowVersion": quote["rowVersion"]}, format="json")
    assert issued.status_code == 201, issued.content
    return issued.data, lambda: _approver(tenant).post(
        f"/api/v1/policies/{issued.data['id']}/installments/1/payment",
        {"paidAt": paid_at, "rowVersion": issued.data["rowVersion"]}, format="json")


@pytest.mark.django_db
@pytest.mark.parametrize("mode,closed_after", [("ON_RENEWAL_ACTIVATION", "activation"), ("ON_RENEWAL_ISSUANCE", "issuance"), ("MANUAL", None)])
def test_renewal_rules_deadlines_and_origin_policy_closure(admin_client, tenant, mode, closed_after):
    approver = make_client(tenant_id=tenant.id, roles=["ADMIN"], scope="q360.read q360.write q360.admin q360.approve", actor_id="biz-approver")
    _publish(admin_client, approver, "renewal.deadlines", {"deadlines": {"acceptance_days": 20, "previous_policy_close": mode}})
    _publish(admin_client, approver, "renewal.rules",
             {"renewal": {"automatic_renewal": True, "medical_inflation_percent": "12", "update_capitals": True}})

    origin_quote = _approved_quote(admin_client, tenant, suffix="BR1")
    origin, activate = _issue_and_activate(tenant, origin_quote, signed_at="2026-06-10T14:00:00Z", paid_at="2026-06-10T16:00:00Z")
    origin = activate().data

    renewal = admin_client.post("/api/v1/quotes/renewals", {"sourcePolicyId": origin["id"]}, format="json")
    assert renewal.status_code == 201, renewal.content
    quote = renewal.data
    assert quote["renewal"]["acceptanceDeadline"] == (datetime.date.today() + datetime.timedelta(days=20)).isoformat()
    assert quote["renewal"]["capitalIndexation"]["medicalInflationPct"] == "12"
    assert quote["renewal"]["deadlines"] == {"acceptance_days": 20, "previous_policy_close": mode}

    # a renovação é uma cotação: criá-la não fecha a apólice de origem
    status = lambda: admin_client.get(f"/api/v1/policies/{origin['id']}").data["status"]  # noqa: E731
    assert status() == "ACTIVE"
    ready = admin_client.get(f"/api/v1/quotes/{quote['id']}").data
    submitted = admin_client.post(f"/api/v1/quotes/{quote['id']}/submit", {"rowVersion": ready["rowVersion"]}, format="json").data
    approved = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/decision",
        {"decision": "APPROVE", "reasonCode": "OK", "rowVersion": submitted["rowVersion"]}, format="json").data
    renewed, pay = _issue_and_activate(tenant, approved, signed_at="2026-06-11T14:00:00Z", paid_at="2026-06-11T16:00:00Z")
    assert status() == ("RENEWED" if closed_after == "issuance" else "ACTIVE")
    assert pay().status_code == 200
    assert status() == ("RENEWED" if closed_after else "ACTIVE")
