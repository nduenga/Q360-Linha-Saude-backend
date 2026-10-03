"""Super administradores: criam e gerem tenants (com dados da empresa e o
primeiro ADMIN) pela API, sem acesso ao servidor. Equipa interna apenas."""
from __future__ import annotations

import pytest
from django.contrib.auth.hashers import make_password
from rest_framework.test import APIClient

from apps.platform_admin.infrastructure.models import PlatformAdmin

PASSWORD = "uma-palavra-passe-longa-1"
SECRET = "platform-tests-signing-secret-32-bytes-min"


@pytest.fixture(autouse=True)
def _keys(settings):
    settings.PLATFORM_ADMIN_JWT_SIGNING_KEY = SECRET
    settings.Q360_JWT_SIGNING_KEY = "staff-tests-signing-secret-32-bytes-minimum"
    settings.OIDC_ALGORITHMS = ["HS256"]


def _admin(email="root@q360.test", name="Root"):
    return PlatformAdmin.objects.create(email=email, name=name, password_hash=make_password(PASSWORD))


def _login(email="root@q360.test", password=PASSWORD):
    response = APIClient().post("/api/v1/platform/auth/login", {"email": email, "password": password}, format="json")
    return response


def _client(email="root@q360.test"):
    response = _login(email)
    assert response.status_code == 200, response.content
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['accessToken']}")
    return client


NEW_TENANT = {
    "code": "acme-seguros",
    "name": "Acme Seguros",
    "profile": {"legalName": "Acme Seguros, S.A.", "nif": "5417000000", "email": "geral@acme.ao", "country": "Angola"},
    "admin": {"name": "Ana Admin", "email": "ana@acme.ao"},
}


def _staff_login(email, password):
    return APIClient().post("/api/v1/auth/login", {"email": email, "password": password}, format="json")


@pytest.mark.django_db
def test_login_and_lockout():
    _admin()
    assert _login(password="errada").status_code == 401
    assert _login().status_code == 200
    for _ in range(5):
        _login(password="errada")
    assert _login().status_code == 401  # bloqueado


@pytest.mark.django_db
def test_create_tenant_gives_the_first_admin_a_working_login():
    _admin()
    client = _client()
    created = client.post("/api/v1/platform/tenants", NEW_TENANT, format="json")
    assert created.status_code == 201, created.content
    body = created.data
    assert body["tenant"]["code"] == "acme-seguros" and body["tenant"]["status"] == "ACTIVE"
    assert body["tenant"]["profile"]["nif"] == "5417000000"
    assert body["admin"]["role"] == "ADMIN" and body["temporaryPassword"]

    logged = _staff_login("ana@acme.ao", body["temporaryPassword"])
    assert logged.status_code == 200, logged.content
    staff = APIClient()
    staff.credentials(HTTP_AUTHORIZATION=f"Bearer {logged.data['accessToken']}")
    assert staff.get("/api/v1/admin/staff-accounts").status_code == 200
    # a palavra-passe só existe na resposta de criação
    detail = client.get(f"/api/v1/platform/tenants/{body['tenant']['id']}")
    assert "temporaryPassword" not in str(detail.data)
    assert detail.data["stats"] == {"staffAccounts": 1, "activeStaffAccounts": 1}
    assert detail.data["accounts"][0]["roles"] == ["ADMIN"]


@pytest.mark.django_db
def test_duplicates_and_validation_are_refused():
    _admin()
    client = _client()
    assert client.post("/api/v1/platform/tenants", NEW_TENANT, format="json").status_code == 201
    assert client.post("/api/v1/platform/tenants", NEW_TENANT, format="json").status_code == 409
    other = {**NEW_TENANT, "code": "outra", "admin": {"name": "X", "email": "ANA@acme.ao"}}
    assert client.post("/api/v1/platform/tenants", other, format="json").status_code == 409  # email único na plataforma
    assert client.post("/api/v1/platform/tenants", {**NEW_TENANT, "code": "Mau Codigo"}, format="json").status_code == 400


@pytest.mark.django_db
def test_tenants_are_isolated_from_each_other():
    _admin()
    client = _client()
    staff = []
    for code, email in (("alfa", "a@alfa.ao"), ("beta", "b@beta.ao")):
        made = client.post("/api/v1/platform/tenants", {**NEW_TENANT, "code": code, "name": code, "admin": {"name": "A", "email": email}}, format="json")
        token = _staff_login(email, made.data["temporaryPassword"]).data["accessToken"]
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        staff.append(c)
    assert staff[0].post("/api/v1/products", {"code": "SO-ALFA", "name": "Alfa"}, format="json").status_code == 201
    assert [p["code"] for p in staff[1].get("/api/v1/products").data["items"]] == []
    assert [p["code"] for p in staff[0].get("/api/v1/products").data["items"]] == ["SO-ALFA"]


@pytest.mark.django_db
def test_suspending_a_tenant_blocks_existing_tokens_and_new_logins():
    _admin()
    client = _client()
    made = client.post("/api/v1/platform/tenants", NEW_TENANT, format="json").data
    tenant_id = made["tenant"]["id"]
    logged = _staff_login("ana@acme.ao", made["temporaryPassword"])
    staff = APIClient()
    staff.credentials(HTTP_AUTHORIZATION=f"Bearer {logged.data['accessToken']}")
    assert staff.get("/api/v1/admin/staff-accounts").status_code == 200

    suspended = client.patch(f"/api/v1/platform/tenants/{tenant_id}", {"status": "SUSPENDED"}, format="json")
    assert suspended.status_code == 200 and suspended.data["status"] == "SUSPENDED"
    assert staff.get("/api/v1/admin/staff-accounts").status_code == 401
    assert _staff_login("ana@acme.ao", made["temporaryPassword"]).status_code == 401

    client.patch(f"/api/v1/platform/tenants/{tenant_id}", {"status": "ACTIVE", "name": "Acme Seguros (novo nome)"}, format="json")
    assert staff.get("/api/v1/admin/staff-accounts").status_code == 200
    assert client.get(f"/api/v1/platform/tenants/{tenant_id}").data["tenant"]["name"] == "Acme Seguros (novo nome)"


@pytest.mark.django_db
def test_token_types_do_not_cross():
    _admin()
    client = _client()
    assert client.get("/api/v1/quotes").status_code == 403  # token de plataforma nas rotas de tenant
    made = client.post("/api/v1/platform/tenants", NEW_TENANT, format="json").data
    token = _staff_login("ana@acme.ao", made["temporaryPassword"]).data["accessToken"]
    staff = APIClient()
    staff.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert staff.get("/api/v1/platform/tenants").status_code in (401, 403)  # staff nas rotas de plataforma
    assert APIClient().get("/api/v1/platform/tenants").status_code in (401, 403)


@pytest.mark.django_db
def test_add_tenant_admin_and_reset_a_tenant_account_password():
    _admin()
    client = _client()
    made = client.post("/api/v1/platform/tenants", NEW_TENANT, format="json").data
    tenant_id = made["tenant"]["id"]
    second = client.post(f"/api/v1/platform/tenants/{tenant_id}/admins", {"name": "Rui", "email": "rui@acme.ao"}, format="json")
    assert second.status_code == 201
    assert _staff_login("rui@acme.ao", second.data["temporaryPassword"]).status_code == 200
    reset = client.post(f"/api/v1/platform/tenants/{tenant_id}/accounts/{made['admin']['id']}/reset-password", {}, format="json")
    assert reset.status_code == 200
    assert _staff_login("ana@acme.ao", made["temporaryPassword"]).status_code == 401
    assert _staff_login("ana@acme.ao", reset.data["temporaryPassword"]).status_code == 200


@pytest.mark.django_db
def test_several_platform_admins_with_safeguards():
    first = _admin()
    client = _client()
    created = client.post("/api/v1/platform/admins", {"name": "Segundo", "email": "segundo@q360.test"}, format="json")
    assert created.status_code == 201, created.content
    assert _login("segundo@q360.test", created.data["temporaryPassword"]).status_code == 200
    assert len(client.get("/api/v1/platform/admins").data) == 2

    assert client.patch(f"/api/v1/platform/admins/{first.id}", {"status": "DISABLED"}, format="json").status_code == 400  # a si próprio
    second_id = created.data["admin"]["id"]
    assert client.patch(f"/api/v1/platform/admins/{second_id}", {"status": "DISABLED"}, format="json").status_code == 200
    assert _login("segundo@q360.test", created.data["temporaryPassword"]).status_code == 401

    # mudar a própria palavra-passe
    assert client.post("/api/v1/platform/me/password", {"currentPassword": "errada", "newPassword": "nova-palavra-passe-9"}, format="json").status_code == 400
    assert client.post("/api/v1/platform/me/password", {"currentPassword": PASSWORD, "newPassword": "curta"}, format="json").status_code == 400
    assert client.post("/api/v1/platform/me/password", {"currentPassword": PASSWORD, "newPassword": "nova-palavra-passe-9"}, format="json").status_code == 204
    assert _login(password="nova-palavra-passe-9").status_code == 200


@pytest.mark.django_db
def test_every_platform_action_is_audited_without_secrets():
    _admin()
    client = _client()
    made = client.post("/api/v1/platform/tenants", NEW_TENANT, format="json").data
    events = client.get("/api/v1/platform/audit?action=platform.tenant_created").data
    assert len(events) == 1 and events[0]["metadata"]["tenantCode"] == "acme-seguros"
    assert made["temporaryPassword"] not in str(client.get("/api/v1/platform/audit").data)
    assert "platform.login_succeeded" in {e["action"] for e in client.get("/api/v1/platform/audit").data}
