"""Servidor SMTP configurado no painel: plataforma, seguradora, criação do tenant, segredos e permissões."""
from __future__ import annotations

from unittest import mock

import pytest
from django.core import mail
from django.core.cache import cache
from django.db import connection
from rest_framework.test import APIClient

from apps.platform_admin.application import email_settings
from tests.platform_admin.test_platform_admin import NEW_TENANT, SECRET, _admin, _client, _staff_login

SMTP = {"host": "smtp.fornecedor.ao", "port": 587, "security": "STARTTLS", "username": "api-user",
        "password": "segredo-smtp-123", "fromAddress": "no-reply@fornecedor.ao", "fromName": "Plataforma"}
TENANT_SMTP = {**SMTP, "host": "smtp.acme.ao", "fromAddress": "seguros@acme.ao", "password": "outro-segredo"}


@pytest.fixture(autouse=True)
def _env(settings):
    settings.PLATFORM_ADMIN_JWT_SIGNING_KEY = SECRET
    settings.Q360_JWT_SIGNING_KEY = "staff-tests-signing-secret-32-bytes-minimum"
    settings.Q360_STAFF_LOGIN_RATE_LIMIT = 0
    cache.clear()


def _tenant(client):
    made = client.post("/api/v1/platform/tenants", NEW_TENANT, format="json")
    assert made.status_code == 201, made.content
    return made.data


def _tenant_admin(made):
    logged = _staff_login("ana@acme.ao", made["temporaryPassword"])
    assert logged.status_code == 200
    admin = APIClient()
    admin.credentials(HTTP_AUTHORIZATION=f"Bearer {logged.data['accessToken']}")
    return admin


def _stored_password(scope_tenant_id=None):
    with connection.cursor() as cursor:
        if scope_tenant_id is None:
            cursor.execute("SELECT password_enc FROM q360.email_settings WHERE tenant_id IS NULL")
        else:
            cursor.execute("SELECT password_enc FROM q360.email_settings WHERE tenant_id = %s", [scope_tenant_id])
        return cursor.fetchone()[0]


@pytest.mark.django_db
def test_platform_smtp_is_saved_encrypted_never_returned_and_used(django_capture_on_commit_callbacks):
    _admin()
    client = _client()
    assert client.get("/api/v1/platform/email-settings").data["configured"] is False
    saved = client.put("/api/v1/platform/email-settings", SMTP, format="json")
    assert saved.status_code == 200, saved.content
    assert saved.data["hasPassword"] is True and saved.data["lastTest"]["ok"] is True
    assert saved.data["effectiveSource"] == "PLATFORM" and "password" not in saved.data
    assert "segredo-smtp-123" not in str(client.get("/api/v1/platform/email-settings").content)
    stored = _stored_password()
    assert stored and "segredo-smtp-123" not in stored
    assert email_settings.decrypt_secret(stored) == "segredo-smtp-123"

    # os emails da plataforma passam a sair com o remetente configurado
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        _tenant(client)
    assert mail.outbox and "no-reply@fornecedor.ao" in mail.outbox[0].from_email


@pytest.mark.django_db
def test_password_is_kept_when_omitted_and_cleared_when_empty():
    _admin()
    client = _client()
    client.put("/api/v1/platform/email-settings", SMTP, format="json")
    before = _stored_password()
    without_password = {k: v for k, v in SMTP.items() if k != "password"}
    client.put("/api/v1/platform/email-settings", {**without_password, "fromName": "Nova"}, format="json")
    assert _stored_password() == before
    cleared = client.put("/api/v1/platform/email-settings", {"password": ""}, format="json")
    assert cleared.data["hasPassword"] is False and _stored_password() == ""


@pytest.mark.django_db
def test_validation_ports_hosts_and_required_fields():
    _admin()
    client = _client()
    url = "/api/v1/platform/email-settings"
    assert client.put(url, {"host": "smtp.x.ao"}, format="json").status_code == 400  # falta o remetente
    assert client.put(url, {**SMTP, "port": 22}, format="json").status_code == 400
    assert client.put(url, {**SMTP, "host": "smtp x.ao"}, format="json").status_code == 400
    assert client.put(url, {**SMTP, "fromAddress": "isto-nao-e-email"}, format="json").status_code == 400
    assert client.put(url, {**SMTP, "security": "TLS13"}, format="json").status_code == 400


@pytest.mark.django_db
def test_internal_hosts_are_refused_outside_development(settings):
    settings.Q360_EMAIL_CONFIG_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.DEBUG = False
    with mock.patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("10.0.0.5", 587))]):
        with pytest.raises(email_settings.EmailSettingsError):
            email_settings.validate_payload(SMTP, existing=None)
    with mock.patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("8.8.8.8", 587))]):
        email_settings.validate_payload(SMTP, existing=None)


@pytest.mark.django_db
def test_a_failed_connection_test_keeps_the_server_out_of_use():
    _admin()
    client = _client()
    with mock.patch.object(email_settings, "check_connection", return_value=(False, "SMTPAuthenticationError: 535")):
        saved = client.put("/api/v1/platform/email-settings", SMTP, format="json")
    assert saved.data["lastTest"] == {"at": mock.ANY, "ok": False, "error": "SMTPAuthenticationError: 535"}
    assert saved.data["effectiveSource"] == "ENV"
    # desativada ou apagada também deixa de ser usada
    ok = client.put("/api/v1/platform/email-settings", SMTP, format="json")
    assert ok.data["effectiveSource"] == "PLATFORM"
    assert client.put("/api/v1/platform/email-settings", {"enabled": False}, format="json").data["effectiveSource"] == "ENV"
    client.put("/api/v1/platform/email-settings", {"enabled": True}, format="json")
    assert client.delete("/api/v1/platform/email-settings").status_code == 204
    assert client.get("/api/v1/platform/email-settings").data["configured"] is False


@pytest.mark.django_db
def test_tenant_smtp_wins_over_platform_and_falls_back_when_removed(django_capture_on_commit_callbacks):
    _admin()
    client = _client()
    client.put("/api/v1/platform/email-settings", SMTP, format="json")
    with django_capture_on_commit_callbacks(execute=True):
        made = _tenant(client)
    tenant_id = made["tenant"]["id"]
    url = f"/api/v1/platform/tenants/{tenant_id}/email-settings"
    assert client.get(url).data["inheritedFrom"] == "PLATFORM"
    assert client.put(url, TENANT_SMTP, format="json").data["effectiveSource"] == "TENANT"

    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        client.post(f"/api/v1/platform/tenants/{tenant_id}/accounts/{made['admin']['id']}/reset-password", {}, format="json")
    assert "seguros@acme.ao" in mail.outbox[-1].from_email  # nome mantém «Q360 - Acme Seguros»
    assert "Acme Seguros" in mail.outbox[-1].from_email

    assert client.delete(url).status_code == 204
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        client.post(f"/api/v1/platform/tenants/{tenant_id}/accounts/{made['admin']['id']}/reset-password", {}, format="json")
    assert "no-reply@fornecedor.ao" in mail.outbox[-1].from_email
    assert client.get(f"/api/v1/platform/tenants/{uuid_zero()}/email-settings").status_code == 404


def uuid_zero():
    return "00000000-0000-0000-0000-000000000001"


@pytest.mark.django_db
def test_creating_a_tenant_with_its_own_smtp(django_capture_on_commit_callbacks):
    _admin()
    client = _client()
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        made = client.post("/api/v1/platform/tenants", {**NEW_TENANT, "emailSettings": TENANT_SMTP}, format="json")
    assert made.status_code == 201, made.content
    assert made.data["emailSettingsWarning"] is None
    assert "seguros@acme.ao" in mail.outbox[0].from_email  # o email de boas-vindas já sai pelo SMTP da seguradora
    url = f"/api/v1/platform/tenants/{made.data['tenant']['id']}/email-settings"
    assert client.get(url).data["effectiveSource"] == "TENANT"


@pytest.mark.django_db
def test_creating_a_tenant_with_a_dead_smtp_warns_but_creates():
    _admin()
    client = _client()
    with mock.patch.object(email_settings, "check_connection", return_value=(False, "TimeoutError: timed out")):
        made = client.post("/api/v1/platform/tenants", {**NEW_TENANT, "emailSettings": TENANT_SMTP}, format="json")
    assert made.status_code == 201 and "TimeoutError" in made.data["emailSettingsWarning"]
    assert client.get(f"/api/v1/platform/tenants/{made.data['tenant']['id']}/email-settings").data["effectiveSource"] == "ENV"


@pytest.mark.django_db
def test_creating_a_tenant_with_invalid_smtp_creates_nothing():
    _admin()
    client = _client()
    made = client.post("/api/v1/platform/tenants", {**NEW_TENANT, "emailSettings": {**TENANT_SMTP, "port": 22}}, format="json")
    assert made.status_code == 400
    assert client.get("/api/v1/platform/tenants").data == []


@pytest.mark.django_db
def test_tenant_admin_manages_only_their_own_smtp_and_tests_to_themselves():
    _admin()
    platform = _client()
    platform.put("/api/v1/platform/email-settings", SMTP, format="json")
    made = _tenant(platform)
    admin = _tenant_admin(made)

    seen = admin.get("/api/v1/admin/email-settings").data
    assert seen["configured"] is False and seen["inheritedFrom"] == "PLATFORM"
    saved = admin.put("/api/v1/admin/email-settings", TENANT_SMTP, format="json")
    assert saved.status_code == 200 and saved.data["effectiveSource"] == "TENANT" and "password" not in saved.data
    assert email_settings.decrypt_secret(_stored_password(made["tenant"]["id"])) == "outro-segredo"
    # a configuração da plataforma não foi tocada
    assert platform.get("/api/v1/platform/email-settings").data["host"] == "smtp.fornecedor.ao"

    mail.outbox.clear()
    tested = admin.post("/api/v1/admin/email-settings/test", {"to": "outra-pessoa@x.ao"}, format="json")
    assert tested.status_code == 200 and tested.data["ok"] is True
    assert mail.outbox[-1].to == ["ana@acme.ao"]  # sempre para o próprio administrador

    assert admin.delete("/api/v1/admin/email-settings").status_code == 204
    assert admin.get("/api/v1/admin/email-settings").data["configured"] is False


@pytest.mark.django_db
def test_permissions_non_admins_and_anonymous_cannot_touch_smtp():
    _admin()
    platform = _client()
    made = _tenant(platform)
    admin = _tenant_admin(made)
    created = admin.post("/api/v1/admin/staff-accounts", {"email": "rui@acme.ao", "name": "Rui", "roles": ["SUBSCRIBER"],
                                                         "password": "Senha-Forte-2026!"}, format="json")
    assert created.status_code == 201
    rui = APIClient()
    rui.credentials(HTTP_AUTHORIZATION=f"Bearer {_staff_login('rui@acme.ao', 'Senha-Forte-2026!').data['accessToken']}")
    assert rui.get("/api/v1/admin/email-settings").status_code == 403
    assert rui.put("/api/v1/admin/email-settings", SMTP, format="json").status_code == 403
    assert APIClient().get("/api/v1/admin/email-settings").status_code in (401, 403)
    # um admin de tenant não entra nas rotas da plataforma
    assert admin.get("/api/v1/platform/email-settings").status_code in (401, 403)
    assert admin.put(f"/api/v1/platform/tenants/{made['tenant']['id']}/email-settings", SMTP, format="json").status_code in (401, 403)


@pytest.mark.django_db
def test_platform_test_message_needs_a_recipient_and_audit_has_no_secrets():
    _admin()
    client = _client()
    client.put("/api/v1/platform/email-settings", SMTP, format="json")
    assert client.post("/api/v1/platform/email-settings/test", {}, format="json").status_code == 400
    mail.outbox.clear()
    result = client.post("/api/v1/platform/email-settings/test", {"to": "eu@fornecedor.ao"}, format="json")
    assert result.status_code == 200 and result.data["ok"] is True and mail.outbox[-1].to == ["eu@fornecedor.ao"]
    audit = str(client.get("/api/v1/platform/audit").data)
    assert "email_settings_updated" in audit and "email_settings_tested" in audit
    assert "segredo-smtp-123" not in audit


@pytest.mark.django_db
def test_health_panel_counts_a_configured_smtp_as_email_done():
    _admin()
    client = _client()
    made = _tenant(client)
    health_url = f"/api/v1/platform/tenants/{made['tenant']['id']}/health"
    client.put(f"/api/v1/platform/tenants/{made['tenant']['id']}/email-settings", TENANT_SMTP, format="json")
    steps = {s["key"]: s for s in client.get(health_url).data["onboarding"]["steps"]}
    assert "Servidor de email por configurar" not in steps["email"]["detail"]


@pytest.mark.django_db
def test_panel_smtp_never_inherits_the_env_credentials(settings):
    settings.Q360_EMAIL_CONFIG_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST_USER = "conta-do-env@gmail.com"
    settings.EMAIL_HOST_PASSWORD = "palavra-do-env"
    row = email_settings.EmailSettings(host="smtp.fornecedor.ao", port=587, security="STARTTLS", username="",
                                       password_enc="", from_address="a@fornecedor.ao", timeout_seconds=20)
    connection = email_settings._connection(row)
    assert connection.username == "" and connection.password == ""
    with_login = email_settings.EmailSettings(host="smtp.fornecedor.ao", port=587, security="STARTTLS", username="api",
                                              password_enc=email_settings.encrypt_secret("minha"),
                                              from_address="a@fornecedor.ao", timeout_seconds=20)
    assert (email_settings._connection(with_login).username, email_settings._connection(with_login).password) == ("api", "minha")
