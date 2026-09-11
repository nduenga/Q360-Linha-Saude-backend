"""Q360-S2-03 acceptance criteria: "Código/tipo/vigência/versão
obrigatórios • Valor inválido recusado"."""
from __future__ import annotations

import pytest


@pytest.mark.django_db
def test_create_pricing_parameter_set_with_all_value_types(admin_client):
    response = admin_client.post(
        "/api/v1/pricing-parameter-sets",
        {
            "code": "BASE-RATES",
            "effectiveFrom": "2026-01-01",
            "parameters": [
                {"code": "BASE_PREMIUM", "valueType": "DECIMAL", "value": "125.50"},
                {"code": "MAX_DEPENDENTS", "valueType": "INTEGER", "value": 5},
                {"code": "ALLOW_WAITING_PERIOD_WAIVER", "valueType": "BOOLEAN", "value": True},
                {"code": "DEFAULT_CURRENCY", "valueType": "TEXT", "value": "AOA"},
                {"code": "TIER_TABLE", "valueType": "JSON", "value": {"tiers": [1, 2, 3]}},
            ],
        },
        format="json",
    )
    assert response.status_code == 201
    body = response.data
    assert set(body.keys()) == {"id", "code", "versionNo", "effectiveFrom", "effectiveTo", "status", "checksum"}
    assert body["versionNo"] == 1
    assert body["status"] == "DRAFT"


@pytest.mark.django_db
def test_decimal_value_must_be_a_string(admin_client):
    response = admin_client.post(
        "/api/v1/pricing-parameter-sets",
        {
            "code": "BAD-DECIMAL",
            "effectiveFrom": "2026-01-01",
            "parameters": [{"code": "X", "valueType": "DECIMAL", "value": 12.5}],
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_duplicate_parameter_codes_within_request_rejected(admin_client):
    response = admin_client.post(
        "/api/v1/pricing-parameter-sets",
        {
            "code": "DUP-PARAM",
            "effectiveFrom": "2026-01-01",
            "parameters": [
                {"code": "X", "valueType": "INTEGER", "value": 1},
                {"code": "X", "valueType": "INTEGER", "value": 2},
            ],
        },
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION-400"


@pytest.mark.django_db
def test_publish_pricing_parameter_set_via_generic_configuration_endpoint(admin_client):
    created = admin_client.post(
        "/api/v1/pricing-parameter-sets",
        {
            "code": "TO-PUBLISH",
            "effectiveFrom": "2026-01-01",
            "parameters": [{"code": "X", "valueType": "INTEGER", "value": 1}],
        },
        format="json",
    ).data

    response = admin_client.post(f"/api/v1/configuration/pricing-parameter-set/{created['id']}/publish")
    assert response.status_code == 200
    assert response.data["status"] == "PUBLISHED"


@pytest.mark.django_db
def test_publish_not_yet_available_config_type_is_not_found(admin_client):
    # rating-table (S4) does not exist yet — must read as NOT-FOUND, not a
    # 500 or an invented "not implemented" response.
    response = admin_client.post(
        "/api/v1/configuration/rating-table/11111111-1111-1111-1111-111111111111/publish"
    )
    assert response.status_code == 404
    assert response.data["code"] == "NOT-FOUND"
