"""App móvel do Portal Cliente (roadmap_mobile.md, Fase 1): descoberta da
seguradora, marca pública, sessão por dispositivo (renovação, fim de sessão,
dispositivos ligados), push e ligações universais. A web continua igual."""
from __future__ import annotations

import contextlib
import datetime
import tempfile
import uuid
from unittest import mock

import jwt
import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.customer_portal.application import notifications_service, push_service
from apps.customer_portal.infrastructure.models import (
    CustomerAccount,
    CustomerDeviceSession,
    CustomerPushDevice,
    PortalNotification,
)
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.models import Tenant
from tests.customer_portal.test_password_login_api import GOOD, NEW, _code, _customer, _first_access, _url
from tests.customer_portal.test_self_service_api import _EMAIL

DEVICE = {"deviceId": "iphone-123", "deviceName": "iPhone da Ana", "platform": "IOS", "appVersion": "1.0.0"}
EXPO = "ExponentPushToken[abcdefghijklmnopqrstuv]"


@pytest.fixture(autouse=True)
def _no_ip_limit(settings):
    settings.CUSTOMER_PORTAL_LOGIN_RATE_LIMIT_PER_IP = 0


def _login(tenant, *, device=DEVICE, password=GOOD, email=_EMAIL):
    body = {"email": email, "password": password}
    if device is not None:
        body["device"] = device
    return APIClient().post(_url(tenant, "login"), body, format="json")


def _refresh(tenant, token, **extra):
    return APIClient().post(_url(tenant, "refresh"), {"refreshToken": token, **extra}, format="json")


def _client(access_token: str) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client


@pytest.fixture
def mobile(admin_client, tenant):
    """Cliente com palavra-passe definida e uma sessão de telemóvel aberta."""
    scope = _customer(admin_client, tenant, "APO-M-001", "960000001LA001")
    assert _first_access(tenant, scope).status_code == 200
    logged = _login(tenant)
    assert logged.status_code == 200, logged.data
    return {"scope": scope, "login": logged.data, "tenant": tenant}


def _account_id(access_token: str) -> uuid.UUID:
    return uuid.UUID(jwt.decode(access_token, options={"verify_signature": False})["sub"])


# ----------------------------------------------------- a web não muda nada
@pytest.mark.django_db
def test_login_without_a_device_keeps_the_web_response(admin_client, tenant):
    scope = _customer(admin_client, tenant, "APO-M-002", "960000002LA002")
    _first_access(tenant, scope)
    response = _login(tenant, device=None)
    assert response.status_code == 200
    assert set(response.data) == {"accessToken", "tokenType", "expiresIn"}
    assert "sid" not in jwt.decode(response.data["accessToken"], options={"verify_signature": False})
    assert CustomerDeviceSession.all_tenants.count() == 0


@pytest.mark.django_db
def test_login_with_a_device_returns_a_refresh_token_and_a_session_bound_access_token(mobile):
    data = mobile["login"]
    assert data["refreshToken"] and data["refreshExpiresIn"] == 90 * 24 * 3600
    claims = jwt.decode(data["accessToken"], options={"verify_signature": False})
    session = CustomerDeviceSession.all_tenants.get(id=claims["sid"])
    assert session.device_id == "iphone-123" and session.platform == "IOS"
    # só o hash fica guardado
    assert data["refreshToken"].split(".", 1)[1] not in (session.token_hash, session.previous_token_hash)
    assert _client(data["accessToken"]).get("/api/v1/customer-portal/dashboard").status_code == 200


@pytest.mark.django_db
def test_logging_in_again_on_the_same_device_replaces_its_session(mobile):
    second = _login(mobile["tenant"])
    assert second.status_code == 200
    assert CustomerDeviceSession.all_tenants.filter(revoked_at__isnull=True).count() == 1
    # a sessão antiga já não renova nem serve
    assert _refresh(mobile["tenant"], mobile["login"]["refreshToken"]).status_code == 401
    assert _client(mobile["login"]["accessToken"]).get("/api/v1/customer-portal/dashboard").status_code == 401


# --------------------------------------------------------------- renovação
@pytest.mark.django_db
def test_refresh_rotates_the_token_and_the_new_pair_works(mobile):
    tenant, first = mobile["tenant"], mobile["login"]
    renewed = _refresh(tenant, first["refreshToken"], appVersion="1.1.0")
    assert renewed.status_code == 200, renewed.data
    assert renewed.data["refreshToken"] != first["refreshToken"]
    assert _client(renewed.data["accessToken"]).get("/api/v1/customer-portal/dashboard").status_code == 200
    again = _refresh(tenant, renewed.data["refreshToken"])
    assert again.status_code == 200
    session = CustomerDeviceSession.all_tenants.get(id=first["refreshToken"].split(".")[0])
    assert session.app_version == "1.1.0"


@pytest.mark.django_db
def test_reusing_an_already_rotated_refresh_token_ends_the_session(mobile):
    tenant, first = mobile["tenant"], mobile["login"]
    renewed = _refresh(tenant, first["refreshToken"])
    assert renewed.status_code == 200
    stolen = _refresh(tenant, first["refreshToken"])  # o token antigo, outra vez
    assert stolen.status_code == 401
    # e o par legítimo também deixa de servir: quem o tinha tem de entrar de novo
    assert _refresh(tenant, renewed.data["refreshToken"]).status_code == 401
    assert _client(renewed.data["accessToken"]).get("/api/v1/customer-portal/dashboard").status_code == 401
    row = CustomerDeviceSession.all_tenants.get(id=first["refreshToken"].split(".")[0])
    assert row.revoked_reason == "REUSE_DETECTED"


@pytest.mark.django_db
def test_refresh_rejects_garbage_a_wrong_secret_and_another_tenant(mobile, admin_client):
    tenant, first = mobile["tenant"], mobile["login"]
    session_id = first["refreshToken"].split(".")[0]
    for bad in ("", "lixo", "nao-uuid.segredo", f"{session_id}.segredo-errado", f"{uuid.uuid4()}.x"):
        assert _refresh(tenant, bad or "x").status_code == 401, bad
    # um palpite errado não termina a sessão verdadeira
    assert _refresh(tenant, first["refreshToken"]).status_code == 200
    other = Tenant.objects.create(id=uuid.uuid4(), code=f"t-{uuid.uuid4().hex[:6]}", name="Outra")
    assert _refresh(other, first["refreshToken"]).status_code == 401


@pytest.mark.django_db
def test_an_idle_session_expires(mobile):
    CustomerDeviceSession.all_tenants.update(expires_at=timezone.now() - datetime.timedelta(seconds=1))
    assert _refresh(mobile["tenant"], mobile["login"]["refreshToken"]).status_code == 401
    assert CustomerDeviceSession.all_tenants.get().revoked_reason == "EXPIRED"


@pytest.mark.django_db
def test_refresh_is_blocked_while_the_account_is_locked(mobile):
    CustomerAccount.all_tenants.update(locked_until=timezone.now() + datetime.timedelta(minutes=5), failed_otp_attempts=5)
    assert _refresh(mobile["tenant"], mobile["login"]["refreshToken"]).status_code == 423


# ------------------------------------------------------------ fim de sessão
@pytest.mark.django_db
def test_logout_ends_the_session_and_is_always_204(mobile):
    tenant, data = mobile["tenant"], mobile["login"]
    out = APIClient().post(_url(tenant, "logout"), {"refreshToken": data["refreshToken"]}, format="json")
    assert out.status_code == 204
    assert _refresh(tenant, data["refreshToken"]).status_code == 401
    assert _client(data["accessToken"]).get("/api/v1/customer-portal/dashboard").status_code == 401
    garbage = APIClient().post(_url(tenant, "logout"), {"refreshToken": "lixo"}, format="json")
    assert garbage.status_code == 204


@pytest.mark.django_db
def test_changing_the_password_ends_every_mobile_session(mobile):
    tenant = mobile["tenant"]
    other_phone = _login(tenant, device={**DEVICE, "deviceId": "android-9", "platform": "ANDROID"})
    assert other_phone.status_code == 200
    client = APIClient()
    assert client.post(_url(tenant, "password-reset/request"), {"email": _EMAIL}, format="json").status_code == 202
    done = client.post(
        _url(tenant, "password-reset/confirm"),
        {"email": _EMAIL, "otp": _code(), "password": NEW, "device": {**DEVICE, "deviceId": "new-phone"}},
        format="json",
    )
    assert done.status_code == 200 and done.data["refreshToken"]
    for old in (mobile["login"], other_phone.data):
        assert _refresh(tenant, old["refreshToken"]).status_code == 401
        assert _client(old["accessToken"]).get("/api/v1/customer-portal/dashboard").status_code == 401
    assert _client(done.data["accessToken"]).get("/api/v1/customer-portal/dashboard").status_code == 200


# --------------------------------------------------- dispositivos ligados
@pytest.mark.django_db
def test_connected_devices_list_and_terminate(mobile):
    tenant, data = mobile["tenant"], mobile["login"]
    other = _login(tenant, device={**DEVICE, "deviceId": "android-9", "deviceName": "Samsung", "platform": "ANDROID"})
    mine = _client(data["accessToken"])

    listed = mine.get("/api/v1/customer-portal/sessions")
    assert listed.status_code == 200
    by_name = {s["deviceName"]: s for s in listed.data["sessions"]}
    assert set(by_name) == {"iPhone da Ana", "Samsung"}
    assert by_name["iPhone da Ana"]["current"] is True and by_name["Samsung"]["current"] is False

    ended = mine.delete(f"/api/v1/customer-portal/sessions/{by_name['Samsung']['id']}")
    assert ended.status_code == 204
    assert _refresh(tenant, other.data["refreshToken"]).status_code == 401
    assert _client(other.data["accessToken"]).get("/api/v1/customer-portal/dashboard").status_code == 401
    assert mine.delete(f"/api/v1/customer-portal/sessions/{by_name['Samsung']['id']}").status_code == 404


@pytest.mark.django_db
def test_a_customer_cannot_end_someone_elses_session(mobile, admin_client, tenant):
    other_scope = _customer(admin_client, tenant, "APO-M-003", "960000003LA003")
    other = CustomerAccount.all_tenants.create(tenant_id=tenant.id, email="outro@example.com", password_hash="x")
    foreign = CustomerDeviceSession.all_tenants.create(
        tenant_id=tenant.id, customer_account=other, device_id="d", token_hash="h",
        expires_at=timezone.now() + datetime.timedelta(days=1),
    )
    response = _client(mobile["login"]["accessToken"]).delete(f"/api/v1/customer-portal/sessions/{foreign.id}")
    assert response.status_code == 404
    assert other_scope  # fixture usada só para garantir o segundo cliente
    assert CustomerDeviceSession.all_tenants.get(id=foreign.id).revoked_at is None


@pytest.mark.django_db
def test_device_rate_limit(mobile, settings):
    settings.CUSTOMER_PORTAL_DEVICE_RATE_LIMIT = 2
    results = [_login(mobile["tenant"], password="errada-errada-1").status_code for _ in range(3)]
    assert results[:2] == [401, 401] and results[2] == 429


@pytest.mark.django_db
def test_login_audit_records_the_device(mobile):
    from apps.foundation.infrastructure.models import AuditEvent

    event = AuditEvent.all_tenants.filter(action="customer_portal.login_succeeded").order_by("-occurred_at").first()
    assert event is not None and event.metadata_json.get("deviceId") == "iphone-123"


# -------------------------------------------------------------------- marca
def _brand(tenant, **branding):
    tenant.settings_json = {"branding": branding}
    tenant.save()
    from apps.platform_admin.application import tenant_settings

    tenant_settings.invalidate(tenant.id)


@pytest.mark.django_db
def test_public_branding(tenant):
    _brand(tenant, primaryColor="#0B3D91", secondaryColor="#FFAA00")
    response = APIClient().get(f"/api/v1/customer-portal/{tenant.id}/branding")
    assert response.status_code == 200
    assert response.data == {
        "tenantId": str(tenant.id), "name": "Test Tenant", "primaryColor": "#0B3D91",
        "secondaryColor": "#FFAA00", "portalEnabled": True, "logoUrl": None,
    }
    assert APIClient().get(f"/api/v1/customer-portal/{uuid.uuid4()}/branding").status_code == 404
    assert APIClient().get(f"/api/v1/customer-portal/{tenant.id}/branding/logo").status_code == 404


@pytest.mark.django_db
def test_branding_serves_the_logo_and_reports_a_disabled_portal(tenant, settings):
    from apps.platform_admin.application import tenant_settings

    media = tempfile.TemporaryDirectory()
    settings.MEDIA_ROOT = media.name
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    key = tenant_settings.store_logo(tenant, png, "image/png")
    _brand(tenant, primaryColor="#0B3D91", logo=key)

    branding = APIClient().get(f"/api/v1/customer-portal/{tenant.id}/branding")
    assert branding.data["logoUrl"].endswith(f"/api/v1/customer-portal/{tenant.id}/branding/logo")
    logo = APIClient().get(f"/api/v1/customer-portal/{tenant.id}/branding/logo")
    assert logo.status_code == 200 and logo["Content-Type"] == "image/png" and logo.content == png

    tenant.settings_json = {"branding": {"primaryColor": "#0B3D91", "logo": key},
                            "limits": {"modules": {"customerPortal": False}}}
    tenant.save()
    tenant_settings.invalidate(tenant.id)
    assert APIClient().get(f"/api/v1/customer-portal/{tenant.id}/branding").data["portalEnabled"] is False
    assert APIClient().get(f"/api/v1/customer-portal/{tenant.id}/branding/logo").status_code == 404
    media.cleanup()


# ---------------------------------------------------------------- descoberta
def _second_insurer(email=_EMAIL, name="Segunda Seguradora"):
    other = Tenant.objects.create(id=uuid.uuid4(), code=f"t-{uuid.uuid4().hex[:6]}", name=name)
    CustomerAccount.all_tenants.create(tenant_id=other.id, email=email)
    return other


def _discover(email):
    return APIClient().post("/api/v1/customer-portal/discover", {"email": email}, format="json")


@pytest.mark.django_db
def test_discover_returns_the_single_insurer_with_its_brand(tenant):
    _brand(tenant, primaryColor="#112233")
    CustomerAccount.all_tenants.create(tenant_id=tenant.id, email=_EMAIL)
    sent = len(mail.outbox)
    response = _discover(_EMAIL.upper())
    assert response.status_code == 200
    assert [i["tenantId"] for i in response.data["insurers"]] == [str(tenant.id)]
    assert response.data["insurers"][0]["primaryColor"] == "#112233"
    assert len(mail.outbox) == sent


@pytest.mark.django_db
def test_discover_with_no_account_or_a_disabled_portal_returns_nothing(tenant):
    assert _discover("ninguem@example.com").data == {"insurers": []}
    CustomerAccount.all_tenants.create(tenant_id=tenant.id, email=_EMAIL)
    tenant.settings_json = {"limits": {"modules": {"customerPortal": False}}}
    tenant.save()
    from apps.platform_admin.application import tenant_settings

    tenant_settings.invalidate(tenant.id)
    assert _discover(_EMAIL).data == {"insurers": []}


@pytest.mark.django_db
def test_discover_with_several_insurers_emails_them_instead_of_listing(tenant):
    CustomerAccount.all_tenants.create(tenant_id=tenant.id, email=_EMAIL)
    other = _second_insurer()
    sent = len(mail.outbox)
    response = _discover(_EMAIL)
    assert response.status_code == 200 and response.data == {"insurers": []}  # igual a «sem conta»
    assert len(mail.outbox) == sent + 1
    message = mail.outbox[-1]
    assert message.to == [_EMAIL]
    assert str(tenant.id) in message.body and str(other.id) in message.body
    assert "Test Tenant" in message.body and "Segunda Seguradora" in message.body


@pytest.mark.django_db
def test_discover_is_rate_limited_per_ip_and_per_email(tenant, settings):
    settings.CUSTOMER_PORTAL_DISCOVER_RATE_LIMIT = 3
    codes = [_discover(f"x{i}@example.com").status_code for i in range(4)]
    assert codes == [200, 200, 200, 429]

    settings.CUSTOMER_PORTAL_DISCOVER_RATE_LIMIT = 0
    settings.CUSTOMER_PORTAL_DISCOVER_RATE_LIMIT_PER_EMAIL = 1
    assert _discover("mesmo@example.com").status_code == 200
    assert _discover("mesmo@example.com").status_code == 429


@pytest.mark.django_db
def test_discover_validates_the_email():
    assert _discover("nao-e-email").status_code == 400


# --------------------------------------------------------------------- push
@pytest.fixture
def customer_context(mobile):
    return {**mobile, "account_id": _account_id(mobile["login"]["accessToken"])}


@contextlib.contextmanager
def _as_customer(ctx):
    """Liga um actor cliente ao tenant, como a autenticação faz (cada pedido da API
    desliga-o no fim, por isso liga-se só à volta de cada chamada ao serviço)."""
    token = CurrentActorProvider.bind(
        Actor(actor_id=str(ctx["account_id"]), tenant_id=TenantId.parse(str(ctx["tenant"].id)), roles=frozenset(),
              scopes=frozenset(), actor_type="CUSTOMER")
    )
    try:
        yield
    finally:
        CurrentActorProvider.reset(token)


def _register(mobile, token=EXPO):
    return _client(mobile["login"]["accessToken"]).post(
        "/api/v1/customer-portal/devices", {"expoToken": token, "platform": "IOS"}, format="json"
    )


def _notify(ctx, key="k1", code="PAYMENT_OVERDUE", title="Pagamento em atraso"):
    with _as_customer(ctx):
        return notifications_service.notify_account(
            account_id=ctx["account_id"], dedupe_key=key, code=code, title=title, body="Detalhe privado",
            link="/portal/pagamentos",
        )


@pytest.mark.django_db
def test_register_and_unregister_a_push_device(mobile):
    assert _register(mobile, "token-invalido").status_code == 400
    created = _register(mobile)
    assert created.status_code == 201 and created.data["active"] is True
    assert _register(mobile).data["id"] == created.data["id"]  # idempotente
    assert CustomerPushDevice.all_tenants.count() == 1
    sid = jwt.decode(mobile["login"]["accessToken"], options={"verify_signature": False})["sid"]
    assert str(CustomerPushDevice.all_tenants.get().device_session_id) == sid

    client = _client(mobile["login"]["accessToken"])
    assert client.delete(f"/api/v1/customer-portal/devices/{created.data['id']}").status_code == 204
    assert CustomerPushDevice.all_tenants.get().active is False
    assert client.delete(f"/api/v1/customer-portal/devices/{uuid.uuid4()}").status_code == 404


@pytest.mark.django_db
def test_a_new_notification_sends_one_push_after_commit_with_no_private_text(
    customer_context, settings, django_capture_on_commit_callbacks
):
    settings.CUSTOMER_PORTAL_PUSH_ENABLED = True
    _register(customer_context)
    with mock.patch("apps.customer_portal.infrastructure.push_sender.post_messages", return_value=[{"status": "ok"}]) as post:
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            assert _notify(customer_context) is True
        assert len(callbacks) == 1
        sent = post.call_args.args[0]
        assert len(sent) == 1 and sent[0]["to"] == EXPO
        assert sent[0]["title"] == "Pagamento em atraso"
        assert "Detalhe privado" not in str(sent)  # o corpo (pode ter dados de saúde) não vai no push
        assert sent[0]["data"]["link"] == "/portal/pagamentos" and sent[0]["data"]["category"] == "PAYMENTS"

        # a mesma notificação outra vez (sync repetido): não duplica nem reenvia
        with django_capture_on_commit_callbacks(execute=True) as again:
            assert _notify(customer_context) is False
        assert again == [] and post.call_count == 1
    assert PortalNotification.all_tenants.filter(customer_account_id=customer_context["account_id"]).count() == 1


@pytest.mark.django_db
def test_push_respects_the_settings_the_preferences_and_unmapped_codes(
    customer_context, settings, django_capture_on_commit_callbacks
):
    _register(customer_context)
    account_id = customer_context["account_id"]
    with mock.patch("apps.customer_portal.infrastructure.push_sender.post_messages", return_value=[{}]) as post:
        with django_capture_on_commit_callbacks(execute=True):
            _notify(customer_context, "a")  # CUSTOMER_PORTAL_PUSH_ENABLED desligado por omissão
        assert post.call_count == 0

        settings.CUSTOMER_PORTAL_PUSH_ENABLED = True
        client = _client(customer_context["login"]["accessToken"])
        prefs = client.get("/api/v1/customer-portal/notification-preferences")
        assert {p["category"] for p in prefs.data["preferences"]} == {"PAYMENTS", "QUOTES", "REQUESTS", "MESSAGES", "POLICIES"}
        assert all(p["enabled"] for p in prefs.data["preferences"])
        off = client.put(
            "/api/v1/customer-portal/notification-preferences",
            {"preferences": [{"category": "PAYMENTS", "enabled": False}]}, format="json",
        )
        assert off.status_code == 200 and {p["category"]: p["enabled"] for p in off.data["preferences"]}["PAYMENTS"] is False
        with django_capture_on_commit_callbacks(execute=True):
            _notify(customer_context, "b")  # pagamentos desligados
            _notify(customer_context, "c", code="POLICY_ISSUED", title="Apólice emitida")  # sem categoria de push
        assert post.call_count == 0

        with django_capture_on_commit_callbacks(execute=True):
            _notify(customer_context, "d", code="NEW_MESSAGE", title="Nova mensagem do seu mediador")
        assert post.call_count == 1
    bad = client.put("/api/v1/customer-portal/notification-preferences",
                     {"preferences": [{"category": "NADA", "enabled": True}]}, format="json")
    assert bad.status_code == 400


@pytest.mark.django_db
def test_expo_reporting_a_dead_token_deactivates_the_device(customer_context, settings, django_capture_on_commit_callbacks):
    settings.CUSTOMER_PORTAL_PUSH_ENABLED = True
    _register(customer_context)
    dead = [{"status": "error", "details": {"error": "DeviceNotRegistered"}}]
    with mock.patch("apps.customer_portal.infrastructure.push_sender.post_messages", return_value=dead):
        with django_capture_on_commit_callbacks(execute=True):
            _notify(customer_context)
    assert CustomerPushDevice.all_tenants.get().active is False


@pytest.mark.django_db
def test_a_push_failure_never_breaks_the_request(customer_context, settings, django_capture_on_commit_callbacks):
    settings.CUSTOMER_PORTAL_PUSH_ENABLED = True
    _register(customer_context)
    with mock.patch("apps.customer_portal.infrastructure.push_sender.post_messages", side_effect=RuntimeError("boom")):
        with django_capture_on_commit_callbacks(execute=True):
            assert _notify(customer_context) is True
    assert PortalNotification.all_tenants.count() == 1


@pytest.mark.django_db
def test_logging_out_stops_the_push_to_that_phone(customer_context, settings, django_capture_on_commit_callbacks):
    settings.CUSTOMER_PORTAL_PUSH_ENABLED = True
    _register(customer_context)
    APIClient().post(_url(customer_context["tenant"], "logout"),
                     {"refreshToken": customer_context["login"]["refreshToken"]}, format="json")
    assert CustomerPushDevice.all_tenants.get().active is False
    with mock.patch("apps.customer_portal.infrastructure.push_sender.post_messages") as post:
        with django_capture_on_commit_callbacks(execute=True):
            _notify(customer_context)
        assert post.call_count == 0


@pytest.mark.django_db
def test_the_same_phone_moves_to_the_account_that_registered_it_last(customer_context, tenant):
    _register(customer_context)
    other = CustomerAccount.all_tenants.create(tenant_id=tenant.id, email="outro@example.com")
    with _as_customer(customer_context):
        push_service.register_device(account_id=other.id, session_id=None, expo_token=EXPO, platform="ANDROID")
    device = CustomerPushDevice.all_tenants.get()
    assert device.customer_account_id == other.id and device.device_session_id is None


@pytest.mark.django_db
def test_sync_command_pushes_state_based_notifications(mobile, admin_client, settings, django_capture_on_commit_callbacks):
    """Prestação em atraso: nasce do estado, por isso só o comando periódico a faz chegar sem a app aberta."""
    from apps.policy.infrastructure.models import PremiumInstallment

    settings.CUSTOMER_PORTAL_PUSH_ENABLED = True
    _register(mobile)
    day = datetime.date.today() - datetime.timedelta(days=30)
    PremiumInstallment.all_tenants.create(
        tenant_id=mobile["tenant"].id, policy_id=mobile["scope"]["policyId"], installment_no=1, period_from=day,
        period_to=day + datetime.timedelta(days=365), due_date=day, amount="500.00", currency_code="AOA",
        status="OVERDUE",
    )

    with mock.patch("apps.customer_portal.infrastructure.push_sender.post_messages", return_value=[{"status": "ok"}]) as post:
        with django_capture_on_commit_callbacks(execute=True):
            call_command("sync_portal_notifications")
        titles = [m["title"] for call in post.call_args_list for m in call.args[0]]
        assert "Pagamento em atraso" in titles
        before = post.call_count
        with django_capture_on_commit_callbacks(execute=True):
            call_command("sync_portal_notifications")  # idempotente: nada de novo, nada reenviado
        assert post.call_count == before


# ---------------------------------------------------------- ligações universais
@pytest.mark.django_db
def test_well_known_files_are_404_until_configured_then_served(settings):
    client = APIClient()
    assert client.get("/.well-known/apple-app-site-association").status_code == 404
    assert client.get("/.well-known/assetlinks.json").status_code == 404

    settings.CUSTOMER_PORTAL_APPLE_APP_IDS = ["ABCDE12345.ao.quote360.cliente"]
    settings.CUSTOMER_PORTAL_ANDROID_PACKAGE = "ao.quote360.cliente"
    settings.CUSTOMER_PORTAL_ANDROID_SHA256 = ["AA:BB"]
    apple = client.get("/.well-known/apple-app-site-association")
    assert apple.status_code == 200 and apple["Content-Type"].startswith("application/json")
    assert apple.json()["applinks"]["details"][0]["appIDs"] == ["ABCDE12345.ao.quote360.cliente"]
    android = client.get("/.well-known/assetlinks.json").json()
    assert android[0]["target"]["package_name"] == "ao.quote360.cliente"
    assert android[0]["target"]["sha256_cert_fingerprints"] == ["AA:BB"]


@pytest.mark.django_db(transaction=True)
def test_invitation_links_use_the_app_domain_and_name_the_insurer_when_configured(admin_client, tenant, settings):
    settings.CUSTOMER_PORTAL_URL = "https://portal.exemplo.ao/portal-cliente"
    settings.CUSTOMER_PORTAL_APP_URL = "https://app.quote360.ao"
    mail.outbox.clear()
    body = {"proposerType": "INDIVIDUAL", "displayName": "Cliente App", "registrationNumber": "023239999LA090",
            "email": "app@convite.ao", "phone": "+244923000000", "dateOfBirth": "1990-01-01"}
    assert admin_client.post("/api/v1/proposers", body, format="json").status_code == 201
    link = f"https://app.quote360.ao/recuperar?email=app%40convite.ao&convite=1&seguradora={tenant.id}"
    assert link in mail.outbox[0].body
    assert "portal.exemplo.ao" not in mail.outbox[0].body
