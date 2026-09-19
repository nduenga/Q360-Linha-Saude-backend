"""POST /api/v1/auth/dev-login — pragmatic bridge so the frontend's
existing LoginPage can obtain a real backend-issued JWT (see
apps/foundation/interfaces/auth_views.py docstring). Not OD-009, not
ART-006 — same posture as every other pragmatic V1 addition.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_valid_admin_credentials_return_working_token(settings):
    settings.OIDC_STATIC_VERIFICATION_KEY = "dev-login-test-secret-32-bytes-min"
    settings.OIDC_ALGORITHMS = ["HS256"]
    client = APIClient()

    resp = client.post(
        "/api/v1/auth/dev-login",
        {"email": "admin@q360.co.ao", "password": "Q360admin2026"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["name"] == "Administrador Q360"
    token = resp.data["accessToken"]

    # The minted token must actually authenticate against a real endpoint.
    authed = APIClient()
    authed.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    me = authed.get("/api/v1/me")
    assert me.status_code == 200
    assert "ADMIN" in me.data["roles"]
    assert "product:manage" in me.data["permissions"]


@pytest.mark.django_db
def test_valid_subscriber_credentials_get_real_doc001_permissions(settings):
    settings.OIDC_STATIC_VERIFICATION_KEY = "dev-login-test-secret-32-bytes-min"
    settings.OIDC_ALGORITHMS = ["HS256"]
    client = APIClient()

    resp = client.post(
        "/api/v1/auth/dev-login",
        {"email": "subscritor@q360.co.ao", "password": "Q360demo2026"},
        format="json",
    )
    assert resp.status_code == 200
    token = resp.data["accessToken"]

    authed = APIClient()
    authed.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    me = authed.get("/api/v1/me")
    assert me.status_code == 200
    assert me.data["roles"] == ["SUBSCRIBER"]
    # DOC-001 real matrix: Subscriber never gets audit:read (unlike the old
    # frontend mock, which incorrectly granted it).
    assert "audit:read" not in me.data["permissions"]
    assert "quote:create" in me.data["permissions"]


@pytest.mark.django_db
def test_wrong_password_is_401_auth_401(settings):
    settings.OIDC_STATIC_VERIFICATION_KEY = "dev-login-test-secret-32-bytes-min"
    settings.OIDC_ALGORITHMS = ["HS256"]
    client = APIClient()

    resp = client.post(
        "/api/v1/auth/dev-login",
        {"email": "admin@q360.co.ao", "password": "wrong"},
        format="json",
    )
    assert resp.status_code == 401
    assert resp.data["code"] == "AUTH-401"


@pytest.mark.django_db
def test_unknown_email_is_401_auth_401(settings):
    settings.OIDC_STATIC_VERIFICATION_KEY = "dev-login-test-secret-32-bytes-min"
    settings.OIDC_ALGORITHMS = ["HS256"]
    client = APIClient()

    resp = client.post(
        "/api/v1/auth/dev-login",
        {"email": "nobody@example.com", "password": "whatever"},
        format="json",
    )
    assert resp.status_code == 401
    assert resp.data["code"] == "AUTH-401"


def test_endpoint_is_404_when_static_key_not_configured(settings):
    settings.OIDC_STATIC_VERIFICATION_KEY = ""
    client = APIClient()

    resp = client.post(
        "/api/v1/auth/dev-login",
        {"email": "admin@q360.co.ao", "password": "Q360admin2026"},
        format="json",
    )
    assert resp.status_code == 404
