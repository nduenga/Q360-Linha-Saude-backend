"""Nova conta e reposição enviam a palavra-passe por email; recuperação por ligação
de uso único; o utilizador muda a palavra-passe temporária."""
from __future__ import annotations

import re
from urllib.parse import unquote

import pytest
from django.core import mail
from rest_framework.test import APIClient

from tests.platform_admin.test_platform_admin import NEW_TENANT, SECRET, _admin, _client, _staff_login

NEW_PASSWORD = "Uma-Senha-Nova-2026"


@pytest.fixture(autouse=True)
def _keys(settings):
    settings.PLATFORM_ADMIN_JWT_SIGNING_KEY = SECRET
    settings.Q360_JWT_SIGNING_KEY = "staff-tests-signing-secret-32-bytes-minimum"
    settings.Q360_STAFF_LOGIN_RATE_LIMIT = 0
    settings.Q360_PLATFORM_URL = "https://q360.exemplo.ao"


def _create(capture):
    _admin()
    mail.outbox.clear()
    with capture(execute=True):
        made = _client().post("/api/v1/platform/tenants", NEW_TENANT, format="json").data
    return made


def _staff_client(email, password):
    logged = _staff_login(email, password)
    assert logged.status_code == 200, logged.content
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {logged.data['accessToken']}")
    return client, logged.data


def _token_from(message) -> str:
    return unquote(re.search(r"token=([^\s]+)", message.body).group(1))


@pytest.mark.django_db
def test_creating_a_tenant_emails_the_admin_the_link_and_password(django_capture_on_commit_callbacks):
    made = _create(django_capture_on_commit_callbacks)
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["ana@acme.ao"]
    assert "https://q360.exemplo.ao/login" in message.body and made["temporaryPassword"] in message.body
    assert "Acme Seguros" in message.from_email


@pytest.mark.django_db
def test_no_email_when_the_tenant_creation_fails(django_capture_on_commit_callbacks):
    _admin()
    client = _client()
    client.post("/api/v1/platform/tenants", NEW_TENANT, format="json")
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        again = client.post("/api/v1/platform/tenants", {**NEW_TENANT, "code": "outra"}, format="json")
    assert again.status_code == 409 and mail.outbox == []


@pytest.mark.django_db
def test_admin_reset_emails_the_new_password_and_user_can_change_it(django_capture_on_commit_callbacks):
    made = _create(django_capture_on_commit_callbacks)
    admin, _ = _staff_client("ana@acme.ao", made["temporaryPassword"])
    created = admin.post("/api/v1/admin/staff-accounts", {"email": "rui@acme.ao", "name": "Rui", "roles": ["SUBSCRIBER"]},
                         format="json")
    assert created.status_code == 201
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        reset = admin.post(f"/api/v1/admin/staff-accounts/{created.data['id']}/reset-password")
    assert reset.status_code == 200
    message = mail.outbox[-1]
    assert message.to == ["rui@acme.ao"] and reset.data["temporaryPassword"] in message.body
    assert _staff_login("rui@acme.ao", created.data["temporaryPassword"]).status_code == 401

    rui, session = _staff_client("rui@acme.ao", reset.data["temporaryPassword"])
    wrong = rui.post("/api/v1/auth/change-password", {"currentPassword": "errada", "newPassword": NEW_PASSWORD}, format="json")
    assert wrong.status_code == 400
    weak = rui.post("/api/v1/auth/change-password",
                    {"currentPassword": reset.data["temporaryPassword"], "newPassword": "curta"}, format="json")
    assert weak.status_code == 400
    changed = rui.post("/api/v1/auth/change-password",
                       {"currentPassword": reset.data["temporaryPassword"], "newPassword": NEW_PASSWORD}, format="json")
    assert changed.status_code == 200 and changed.data["refreshToken"]
    assert _staff_login("rui@acme.ao", reset.data["temporaryPassword"]).status_code == 401
    assert _staff_login("rui@acme.ao", NEW_PASSWORD).status_code == 200
    # a sessão antiga foi terminada, a nova funciona
    assert APIClient().post("/api/v1/auth/refresh", {"refreshToken": session["refreshToken"]}, format="json").status_code == 401
    assert APIClient().post("/api/v1/auth/refresh", {"refreshToken": changed.data["refreshToken"]},
                            format="json").status_code == 200


@pytest.mark.django_db
def test_account_created_with_a_chosen_password_is_not_emailed(django_capture_on_commit_callbacks):
    made = _create(django_capture_on_commit_callbacks)
    admin, _ = _staff_client("ana@acme.ao", made["temporaryPassword"])
    mail.outbox.clear()
    admin.post("/api/v1/admin/staff-accounts",
               {"email": "rui@acme.ao", "name": "Rui", "roles": ["SUBSCRIBER"], "password": NEW_PASSWORD}, format="json")
    assert mail.outbox == []


@pytest.mark.django_db
def test_forgot_password_is_generic_and_the_link_works_once(django_capture_on_commit_callbacks):
    made = _create(django_capture_on_commit_callbacks)
    client = APIClient()
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        unknown = client.post("/api/v1/auth/forgot-password", {"email": "ninguem@acme.ao"}, format="json")
        known = client.post("/api/v1/auth/forgot-password", {"email": "ANA@acme.ao"}, format="json")
    assert unknown.status_code == known.status_code == 202 and unknown.content == known.content
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["ana@acme.ao"]
    token = _token_from(mail.outbox[0])

    assert client.post("/api/v1/auth/reset-password", {"token": token, "newPassword": "curta"}, format="json").status_code == 400
    done = client.post("/api/v1/auth/reset-password", {"token": token, "newPassword": NEW_PASSWORD}, format="json")
    assert done.status_code == 204
    assert _staff_login("ana@acme.ao", made["temporaryPassword"]).status_code == 401
    assert _staff_login("ana@acme.ao", NEW_PASSWORD).status_code == 200
    again = client.post("/api/v1/auth/reset-password", {"token": token, "newPassword": "Outra-Senha-2026x"}, format="json")
    assert again.status_code == 400  # uso único


@pytest.mark.django_db
def test_recovery_link_rejects_garbage_expiry_and_suspended_tenants(django_capture_on_commit_callbacks, settings):
    _create(django_capture_on_commit_callbacks)
    client = APIClient()
    assert client.post("/api/v1/auth/reset-password", {"token": "lixo", "newPassword": NEW_PASSWORD},
                       format="json").status_code == 400
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        client.post("/api/v1/auth/forgot-password", {"email": "ana@acme.ao"}, format="json")
    token = _token_from(mail.outbox[0])
    settings.Q360_STAFF_RECOVERY_TTL_MINUTES = -1
    assert client.post("/api/v1/auth/reset-password", {"token": token, "newPassword": NEW_PASSWORD},
                       format="json").status_code == 400
    settings.Q360_STAFF_RECOVERY_TTL_MINUTES = 30
    platform = _client()
    tenant_id = platform.get("/api/v1/platform/tenants").data[0]["id"]
    platform.patch(f"/api/v1/platform/tenants/{tenant_id}",
                   {"status": "SUSPENDED", "suspensionReason": "Falta de pagamento da subscrição"}, format="json")
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post("/api/v1/auth/forgot-password", {"email": "ana@acme.ao"}, format="json").status_code == 202
    assert mail.outbox == []


@pytest.mark.django_db
def test_platform_admin_can_recover_too(django_capture_on_commit_callbacks):
    _admin()
    mail.outbox.clear()
    client = APIClient()
    with django_capture_on_commit_callbacks(execute=True):
        client.post("/api/v1/auth/forgot-password", {"email": "root@q360.test"}, format="json")
    token = _token_from(mail.outbox[0])
    assert client.post("/api/v1/auth/reset-password", {"token": token, "newPassword": NEW_PASSWORD},
                       format="json").status_code == 204
    assert _staff_login("root@q360.test", NEW_PASSWORD).data["accountType"] == "PLATFORM"


@pytest.mark.django_db
def test_forgot_password_is_rate_limited(settings):
    settings.Q360_STAFF_RECOVERY_RATE_LIMIT = 2
    client = APIClient()
    codes = [client.post("/api/v1/auth/forgot-password", {"email": "x@acme.ao"}, format="json").status_code
             for _ in range(4)]
    assert codes == [202, 202, 429, 429]
