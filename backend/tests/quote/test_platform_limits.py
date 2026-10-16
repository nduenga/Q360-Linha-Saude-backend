"""Tetos do fornecedor sobre a configuração dos tenants: comissão de
mediação no modelo actuarial (ao submeter e ao aprovar) e idades dos
dependentes nas regras de elegibilidade (ao publicar)."""
from __future__ import annotations

import json

import pytest
from django.utils import timezone

from apps.business_config.seed.actuarial_model import build_actuarial_model
from apps.foundation.infrastructure.models import PlatformParameterVersion
from tests.quote.conftest import make_client
from tests.quote.test_business_config_e2e import BASE, SCOPE

COMMISSION = "limits.max_acquisition_commission_pct"


def _platform_value(code: str, value, version_no: int = 1) -> None:
    PlatformParameterVersion.objects.create(
        code=code, version_no=version_no, status=PlatformParameterVersion.PUBLISHED, value_json=value,
        effective_from=timezone.now(), reason="Teto definido para o teste", created_by="maker", decided_by="checker",
        decided_at=timezone.now(),
    )


@pytest.fixture
def approver(tenant):
    return make_client(tenant_id=tenant.id, roles=["ADMIN"], scope=SCOPE, actor_id="approver-1")


@pytest.mark.django_db
def test_commission_above_the_platform_cap_cannot_be_submitted_or_approved(admin_client, approver):
    model = build_actuarial_model()
    commissions = {s: row["acquisition_commission"] for s, row in model["assumptions"]["loadings"].items()}
    assert all(c is not None for c in commissions.values())
    created = admin_client.post(BASE, {"configKey": "pricing.actuarial_model", "value": model,
                                       "effectiveFrom": "2026-01-01"}, format="json")
    assert created.status_code == 201, created.data
    cid = created.data["id"]
    assert admin_client.post(f"{BASE}/{cid}", {"action": "submit"}, format="json").status_code == 200

    # O fornecedor baixa o teto depois da submissão: a aprovação já o respeita.
    lowest = min(commissions.values())
    _platform_value(COMMISSION, format(lowest * 100 / 2, "f"))
    refused = approver.post(f"{BASE}/{cid}/approve")
    assert refused.status_code == 400 and COMMISSION in refused.data["detail"]

    second = admin_client.post(BASE, {"configKey": "pricing.actuarial_model", "value": model,
                                      "effectiveFrom": "2026-01-01"}, format="json").data
    blocked = admin_client.post(f"{BASE}/{second['id']}", {"action": "submit"}, format="json")
    assert blocked.status_code == 400 and "Comissão de mediação" in blocked.data["detail"]


def _rule(client, code: str, config: dict):
    created = client.post(
        "/api/v1/rule-versions",
        {"code": code, "name": code, "ruleDomain": "ELIGIBILITY", "effectiveFrom": "2026-01-01",
         "artifactType": "JSON", "artifactRef": json.dumps(config)},
        format="json",
    ).data
    return client.post(f"/api/v1/configuration/rule-version/{created['id']}/publish")


@pytest.mark.django_db
def test_eligibility_rules_cannot_exceed_majority_or_the_proof_cap(admin_client):
    over_majority = _rule(admin_client, "ELIG-A", {"categoryRules": {"CHILD": {"maxAgeWithoutProof": 21}}})
    assert over_majority.status_code == 400 and "maioridade" in over_majority.data["detail"]
    corporate = _rule(admin_client, "ELIG-B", {
        "categoryRules": {"CHILD": {"maxAgeWithoutProof": 18, "maxAgeWithProof": 25}},
        "corporateOverrides": {"org-1": {"categoryRules": {"CHILD": {"maxAgeWithProof": 30}}}},
    })
    assert corporate.status_code == 400 and "exceção corporativa" in corporate.data["detail"]
    assert _rule(admin_client, "ELIG-C", {"categoryRules": {"CHILD": {"maxAgeWithoutProof": 18,
                                                                     "maxAgeWithProof": 27}}}).status_code == 200
