"""Decisão em lote (cap. 9): cada cotação segue a regra individual e falha sozinha."""
from __future__ import annotations

import uuid

import pytest

from tests.policy.test_issuance import _approver
from tests.policy.test_manual_v2_guarantees import _submitted, _task


@pytest.mark.django_db
def test_batch_decision_reports_each_quote(admin_client, tenant):
    first, _, _ = _submitted(admin_client, suffix="B1")
    tasks = [_task(admin_client, first["id"])["id"]]
    missing = str(uuid.uuid4())

    own = admin_client.post("/api/v1/reviews/decisions", {
        "taskIds": tasks, "decision": "APPROVE", "reasonCode": "OK",
    }, format="json")
    assert own.status_code == 200, own.data
    assert own.data["decided"] == [] and len(own.data["failed"]) == 1, "quem submeteu nunca decide"

    result = _approver(tenant).post("/api/v1/reviews/decisions", {
        "taskIds": [*tasks, missing], "decision": "APPROVE", "reasonCode": "OK",
    }, format="json")
    assert result.status_code == 200, result.data
    assert [item["quoteId"] for item in result.data["decided"]] == [first["id"]]
    assert all(item["status"] == "APPROVED" for item in result.data["decided"])
    assert [item["taskId"] for item in result.data["failed"]] == [missing]
