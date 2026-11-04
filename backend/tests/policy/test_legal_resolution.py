from __future__ import annotations

import datetime
import io

import pytest
from django.core.management import call_command

from apps.policy.application import issuance_service
from apps.policy.application import lifecycle_service
from tests.policy.test_issuance import _SIGN_BODY, _approved_quote, _approver


def _issue_policy(admin_client, tenant, monkeypatch, *, suffix: str, frequency: str) -> dict:
    quote = _approved_quote(admin_client, tenant, suffix=suffix)
    today = datetime.date.today()
    fixed_now = datetime.datetime.combine(today, datetime.time(12), tzinfo=datetime.timezone.utc)
    monkeypatch.setattr(issuance_service, "timezone_now", lambda: fixed_now)
    response = _approver(tenant).post(
        f"/api/v1/quotes/{quote['id']}/policy",
        {
            **_SIGN_BODY,
            "signedAt": fixed_now.isoformat(),
            "paymentFrequency": frequency,
            "rowVersion": quote["rowVersion"],
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    return {**response.data, "memberId": quote["memberId"], "signedDate": today}


@pytest.mark.django_db
def test_overdue_initial_premium_is_resolved_and_cannot_be_paid_late(
    admin_client, tenant, monkeypatch
):
    policy = _issue_policy(admin_client, tenant, monkeypatch, suffix="LAW-FIRST", frequency="ANUAL")

    monkeypatch.setattr(
        lifecycle_service.timezone,
        "localdate",
        lambda: policy["signedDate"] + datetime.timedelta(days=1),
    )
    output = io.StringIO()
    call_command("premium_overdue_scan", stdout=output)
    assert "1 policy(ies) resolved by law" in output.getvalue()

    current = admin_client.get(f"/api/v1/policies/{policy['id']}").data
    assert current["status"] == "RESOLVED_BY_LAW"
    assert current["resolvedByLaw"] is True
    assert current["resolvedEffectiveFrom"] == policy["signedDate"].isoformat()
    assert current["resolutionReason"] == "INITIAL_PREMIUM"
    assert current["legalBasis"] == "ART_18_1"
    assert current["refundStatus"] == "NOT_DUE"

    late_payment = _approver(tenant).post(
        f"/api/v1/policies/{policy['id']}/installments/1/payment",
        {
            "paidAt": datetime.datetime.combine(
                policy["signedDate"], datetime.time(15), tzinfo=datetime.timezone.utc
            ).isoformat(),
            "rowVersion": policy["rowVersion"],
        },
        format="json",
    )
    assert late_payment.status_code == 409
    assert admin_client.get(f"/api/v1/policies/{policy['id']}").data["status"] == "RESOLVED_BY_LAW"


@pytest.mark.django_db
def test_overdue_followup_installment_resolves_on_due_date_and_limits_coverage(
    admin_client, tenant, monkeypatch
):
    policy = _issue_policy(admin_client, tenant, monkeypatch, suffix="LAW-NEXT", frequency="MENSAL")
    payment = _approver(tenant).post(
        f"/api/v1/policies/{policy['id']}/installments/1/payment",
        {
            "paidAt": datetime.datetime.combine(
                policy["signedDate"], datetime.time(15), tzinfo=datetime.timezone.utc
            ).isoformat(),
            "rowVersion": policy["rowVersion"],
        },
        format="json",
    )
    assert payment.status_code == 200, payment.data

    installments = admin_client.get(f"/api/v1/policies/{policy['id']}/installments").data
    due_date = datetime.date.fromisoformat(next(
        item["dueDate"] for item in installments if item["installmentNo"] == 2
    ))
    from apps.policy.infrastructure.models import Policy as PolicyModel
    from apps.policy.application.lifecycle_service import resolve_policy_for_overdue_premium
    from apps.foundation.application.context import CurrentActorProvider
    from apps.foundation.domain.actor import Actor
    from apps.foundation.domain.permissions import Role
    from apps.foundation.domain.scopes import Scope
    from apps.foundation.domain.tenant import TenantId

    token = CurrentActorProvider.bind(Actor(
        actor_id="test-scheduler",
        tenant_id=TenantId(tenant.id),
        actor_type="SYSTEM",
        roles=frozenset({Role.ADMIN}),
        scopes=frozenset({Scope.READ, Scope.WRITE}),
    ))
    try:
        assert resolve_policy_for_overdue_premium(
            policy=PolicyModel(id=policy["id"]),
            today=due_date + datetime.timedelta(days=1),
        )
        assert not resolve_policy_for_overdue_premium(
            policy=PolicyModel(id=policy["id"]),
            today=due_date + datetime.timedelta(days=1),
        )
    finally:
        CurrentActorProvider.reset(token)

    current = admin_client.get(f"/api/v1/policies/{policy['id']}").data
    assert current["status"] == "RESOLVED_BY_LAW"
    assert current["resolvedEffectiveFrom"] == due_date.isoformat()
    assert current["resolutionReason"] == "INSTALLMENT"
    assert current["legalBasis"] == "ART_18_3"
    late_payment = _approver(tenant).post(
        f"/api/v1/policies/{policy['id']}/installments/2/payment",
        {
            "paidAt": datetime.datetime.combine(
                due_date, datetime.time(15), tzinfo=datetime.timezone.utc
            ).isoformat(),
            "paymentMethod": "TRANSFERENCIA",
        },
        format="json",
    )
    assert late_payment.status_code == 409

    historical = admin_client.get(
        f"/api/v1/policies/{policy['id']}/coverage"
        f"?memberId={policy['memberId']}&date={(due_date - datetime.timedelta(days=1)).isoformat()}"
    )
    assert historical.data["covered"] is True
    current_day = admin_client.get(
        f"/api/v1/policies/{policy['id']}/coverage"
        f"?memberId={policy['memberId']}&date={due_date.isoformat()}"
    )
    assert current_day.data["covered"] is False
    assert current_day.data["reasonCode"] == "POLICY_RESOLVED_BY_LAW"
