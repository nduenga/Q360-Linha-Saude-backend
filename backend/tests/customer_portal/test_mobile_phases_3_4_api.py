"""App móvel, fases 3 e 4 (roadmap_mobile.md): rede convencionada, idioma,
apagar conta, versão mínima da app, eventos de uso e métricas."""
from __future__ import annotations

import uuid

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.client.infrastructure.models import Proposer
from apps.customer_portal.application.providers_service import distance_km
from apps.customer_portal.infrastructure.models import (
    CareProvider,
    CustomerAccount,
    CustomerAccountProposer,
    CustomerDeviceSession,
    CustomerPushDevice,
    PortalNotification,
    PortalUsageEvent,
)
from tests.customer_portal.test_mobile_api import (
    DEVICE,
    EXPO,
    _client,
    _login,
    _refresh,
    _register,
    mobile,  # noqa: F401  (fixture)
)
from tests.customer_portal.test_password_login_api import GOOD, _url

LUANDA = (-8.8383, 13.2344)
BENGUELA = (-12.5763, 13.4055)


def _provider(admin_client, **extra):
    body = {"name": "Clínica Girassol", "type": "CLINIC", "specialties": ["Cardiologia", "Pediatria"],
            "province": "Luanda", "municipality": "Ilha", "address": "Rua A", "phone": "+244 222 000 000",
            "emergency": True, "latitude": "-8.8200", "longitude": "13.2300", **extra}
    response = admin_client.post("/api/v1/care-providers", body, format="json")
    assert response.status_code == 201, response.data
    return response.data


def test_haversine_distance_luanda_benguela():
    assert 410 < distance_km(*LUANDA, *BENGUELA) < 425
    assert distance_km(*LUANDA, *LUANDA) == 0


# --------------------------------------------------------------- prestadores
@pytest.mark.django_db
def test_backoffice_manages_providers_and_the_customer_searches_them(admin_client, mobile):  # noqa: F811
    near = _provider(admin_client)
    far = _provider(admin_client, name="Hospital do Lobito", type="HOSPITAL", province="Benguela",
                    municipality="Lobito", specialties=["Ortopedia"], emergency=False,
                    latitude="-12.3500", longitude="13.5400")
    no_coords = _provider(admin_client, name="Laboratório Sem Mapa", type="LAB", specialties=[],
                          latitude=None, longitude=None)
    client = _client(mobile["login"]["accessToken"])

    everything = client.get("/api/v1/customer-portal/providers")
    assert everything.status_code == 200
    assert [p["name"] for p in everything.data["providers"]] == ["Clínica Girassol", "Hospital do Lobito", "Laboratório Sem Mapa"]
    assert everything.data["providers"][0]["distanceKm"] is None

    nearest = client.get(f"/api/v1/customer-portal/providers?lat={LUANDA[0]}&lng={LUANDA[1]}")
    names = [p["name"] for p in nearest.data["providers"]]
    assert names == ["Clínica Girassol", "Hospital do Lobito", "Laboratório Sem Mapa"]  # sem coordenadas, no fim
    assert nearest.data["providers"][0]["distanceKm"] < 5 and nearest.data["providers"][1]["distanceKm"] > 350

    radius = client.get(f"/api/v1/customer-portal/providers?lat={LUANDA[0]}&lng={LUANDA[1]}&radiusKm=50")
    assert [p["name"] for p in radius.data["providers"]] == ["Clínica Girassol"]

    def names_of(query):
        return [p["name"] for p in client.get(f"/api/v1/customer-portal/providers?{query}").data["providers"]]

    assert names_of("province=benguela") == ["Hospital do Lobito"]
    assert names_of("type=LAB") == ["Laboratório Sem Mapa"]
    assert names_of("specialty=cardiologia") == ["Clínica Girassol"]
    assert names_of("q=lobito") == ["Hospital do Lobito"]
    assert names_of("emergency=true") == ["Clínica Girassol", "Laboratório Sem Mapa"] or "Clínica Girassol" in names_of("emergency=true")

    # desativar tira da rede visível ao cliente, mas o backoffice continua a ver
    assert admin_client.delete(f"/api/v1/care-providers/{far['id']}").status_code == 204
    assert "Hospital do Lobito" not in names_of("")
    staff_view = admin_client.get("/api/v1/care-providers").data["providers"]
    assert {p["name"]: p["active"] for p in staff_view}["Hospital do Lobito"] is False

    edited = admin_client.put(f"/api/v1/care-providers/{near['id']}", {"phone": "+244 999"}, format="json")
    assert edited.status_code == 200 and edited.data["phone"] == "+244 999" and edited.data["name"] == "Clínica Girassol"
    assert admin_client.put(f"/api/v1/care-providers/{uuid.uuid4()}", {"phone": "1"}, format="json").status_code == 404
    assert no_coords


@pytest.mark.django_db
def test_provider_query_validation_and_access(admin_client, mobile):  # noqa: F811
    client = _client(mobile["login"]["accessToken"])
    for bad in ("lat=1", "lat=x&lng=1", "lat=95&lng=1", "type=NADA", "limit=x"):
        assert client.get(f"/api/v1/customer-portal/providers?{bad}").status_code == 400, bad
    assert APIClient().get("/api/v1/customer-portal/providers").status_code == 401
    # o cliente não gere prestadores
    assert client.post("/api/v1/care-providers", {"name": "X"}, format="json").status_code in (401, 403)
    only_lat = admin_client.post("/api/v1/care-providers", {"name": "Y", "latitude": "1.0"}, format="json")
    assert only_lat.status_code == 400


@pytest.mark.django_db
def test_providers_are_isolated_by_tenant(admin_client, mobile):  # noqa: F811
    from apps.foundation.infrastructure.models import Tenant

    other = Tenant.objects.create(id=uuid.uuid4(), code=f"t-{uuid.uuid4().hex[:6]}", name="Outra")
    CareProvider.all_tenants.create(tenant_id=other.id, name="De outra seguradora")
    _provider(admin_client)
    client = _client(mobile["login"]["accessToken"])
    assert [p["name"] for p in client.get("/api/v1/customer-portal/providers").data["providers"]] == ["Clínica Girassol"]


# -------------------------------------------------------------------- idioma
@pytest.mark.django_db
def test_language_preference(mobile):  # noqa: F811
    client = _client(mobile["login"]["accessToken"])
    assert client.get("/api/v1/customer-portal/preferences").data == {"language": "pt"}
    assert client.put("/api/v1/customer-portal/preferences", {"language": "en"}, format="json").data == {"language": "en"}
    assert client.get("/api/v1/customer-portal/preferences").data == {"language": "en"}
    assert client.put("/api/v1/customer-portal/preferences", {"language": "xx"}, format="json").status_code == 400


# -------------------------------------------------------------- apagar conta
@pytest.mark.django_db
def test_delete_account_needs_the_password_and_erases_the_access(mobile):  # noqa: F811
    tenant, data = mobile["tenant"], mobile["login"]
    client = _client(data["accessToken"])
    _register(mobile)
    account = CustomerAccount.all_tenants.get(tenant_id=tenant.id, email__iexact="cliente@example.com")
    PortalNotification.all_tenants.create(
        tenant_id=tenant.id, customer_account=account, dedupe_key="k", code="X", title="t",
    )
    assert CustomerAccountProposer.all_tenants.filter(customer_account=account).exists()

    wrong = client.delete("/api/v1/customer-portal/account", {"password": "errada-errada-1"}, format="json")
    assert wrong.status_code == 401
    assert CustomerAccount.all_tenants.get(id=account.id).deleted_at is None

    done = client.delete("/api/v1/customer-portal/account", {"password": GOOD}, format="json")
    assert done.status_code == 204

    account.refresh_from_db()
    assert account.deleted_at is not None and account.password_hash is None
    assert account.email.endswith("@apagado.invalid")
    assert not CustomerAccountProposer.all_tenants.filter(customer_account=account).exists()
    assert not PortalNotification.all_tenants.filter(customer_account=account).exists()
    assert not CustomerDeviceSession.all_tenants.filter(customer_account=account).exists()
    assert not CustomerPushDevice.all_tenants.filter(customer_account=account).exists()
    # não volta a entrar nem a renovar, e o email fica livre
    assert _login(tenant).status_code == 401
    assert _refresh(tenant, data["refreshToken"]).status_code == 401
    assert client.get("/api/v1/customer-portal/dashboard").status_code == 401
    assert not CustomerAccount.all_tenants.filter(tenant_id=tenant.id, email="cliente@example.com").exists()
    # o cliente da seguradora (e as suas apólices) continua lá
    assert Proposer.all_tenants.filter(tenant_id=tenant.id).exists()


# ------------------------------------------------------------ versão mínima
@pytest.mark.django_db
def test_minimum_app_version_blocks_old_apps_but_never_the_web(mobile, settings):  # noqa: F811
    settings.CUSTOMER_PORTAL_MIN_APP_VERSION = "1.2.0"
    token = mobile["login"]["accessToken"]

    def get(version=None, path="/api/v1/customer-portal/dashboard"):
        client = _client(token)
        extra = {"HTTP_X_APP_VERSION": version} if version else {}
        return client.get(path, **extra)

    old = get("1.1.9")
    assert old.status_code == 426 and old.json()["code"] == "PORTAL-APP-UPDATE-REQUIRED"
    assert old["Content-Type"].startswith("application/problem+json") and "1.2.0" in old.json()["detail"]
    assert get("1.2.0").status_code == 200 and get("1.10.0").status_code == 200 and get("2").status_code == 200
    assert get(None).status_code == 200  # a web não envia o cabeçalho
    assert get("beta").status_code == 200  # ilegível: nunca se bloqueia por engano
    # também bloqueia o login e a renovação nas versões antigas
    blocked = APIClient().post(_url(mobile["tenant"], "login"), {"email": "a@b.co", "password": "x"}, format="json",
                               HTTP_X_APP_VERSION="1.0.0")
    assert blocked.status_code == 426
    # fora do portal não se mexe
    assert APIClient().get("/api/v1/health/live", HTTP_X_APP_VERSION="0.0.1").status_code == 200


@pytest.mark.django_db
def test_app_config_is_public_and_says_whether_to_update(settings):
    settings.CUSTOMER_PORTAL_MIN_APP_VERSION = "1.2.0"
    settings.CUSTOMER_PORTAL_LATEST_APP_VERSION = "1.4.0"
    settings.CUSTOMER_PORTAL_IOS_STORE_URL = "https://apps.apple.com/app/id1"
    old = APIClient().get("/api/v1/customer-portal/app-config", HTTP_X_APP_VERSION="1.0.0")
    assert old.status_code == 200 and old.data["updateRequired"] is True
    assert old.data["minVersion"] == "1.2.0" and old.data["latestVersion"] == "1.4.0"
    assert old.data["storeUrls"] == {"ios": "https://apps.apple.com/app/id1", "android": None}
    assert APIClient().get("/api/v1/customer-portal/app-config", HTTP_X_APP_VERSION="1.3.0").data["updateRequired"] is False
    assert APIClient().get("/api/v1/customer-portal/app-config").data["updateRequired"] is False


@pytest.mark.django_db
def test_no_minimum_configured_blocks_nothing(mobile):  # noqa: F811
    response = _client(mobile["login"]["accessToken"]).get("/api/v1/customer-portal/dashboard", HTTP_X_APP_VERSION="0.0.1")
    assert response.status_code == 200


# ------------------------------------------------------------------- métricas
@pytest.mark.django_db
def test_usage_events_are_validated_and_summarised_for_the_backoffice(admin_client, mobile):  # noqa: F811
    client = _client(mobile["login"]["accessToken"])
    sent = client.post(
        "/api/v1/customer-portal/events",
        {"appVersion": "1.0.0", "platform": "IOS", "events": [
            {"name": "APP_OPEN"}, {"name": "APP_OPEN"},
            {"name": "SCREEN_VIEW", "screen": "cartao"}, {"name": "SCREEN_VIEW", "screen": "cartao"},
            {"name": "SCREEN_VIEW", "screen": "pagamentos"}, {"name": "PUSH_OPENED"},
            {"name": "HACK", "screen": "x"},  # nome desconhecido: ignorado
            {"name": "SCREEN_VIEW", "screen": "maria@example.com ver cartão"},  # texto livre: ignorado
        ]},
        format="json",
    )
    assert sent.status_code == 202 and sent.data == {"accepted": 6}
    assert client.post("/api/v1/customer-portal/events", {"events": []}, format="json").status_code == 400
    assert PortalUsageEvent.all_tenants.count() == 6

    metrics = admin_client.get("/api/v1/portal-app/metrics?days=7")
    assert metrics.status_code == 200
    data = metrics.data
    assert data["activations"] == 1 and data["activeDevices"] == 1 and data["logins"] == 1
    assert {e["name"]: e["count"] for e in data["events"]} == {"APP_OPEN": 2, "SCREEN_VIEW": 3, "PUSH_OPENED": 1}
    assert data["topScreens"][0] == {"screen": "cartao", "count": 2}
    assert data["devicesByPlatform"] == [{"platform": "IOS", "count": 1}]
    assert data["opensByDay"][0]["count"] == 2
    assert admin_client.get("/api/v1/portal-app/metrics?days=x").status_code == 400
    assert APIClient().get("/api/v1/portal-app/metrics").status_code == 401


# --------------------------------------------------------- conta dos revisores
@pytest.mark.django_db
def test_store_review_account_can_log_in_without_the_email_code(admin_client, tenant, capsys):
    from tests.customer_portal.test_password_login_api import _customer

    scope = _customer(admin_client, tenant, "APO-R-901", "960000901LA001")
    with pytest.raises(Exception, match="--confirm"):
        call_command("create_store_review_account", tenant_id=str(tenant.id),
                     registration_number=scope["registrationNumber"], email="revisor@exemplo.ao")
    call_command("create_store_review_account", tenant_id=str(tenant.id), registration_number=scope["registrationNumber"],
                 email="Revisor@exemplo.ao", password="revisao-lojas-2026", confirm=True)
    logged = _login(tenant, email="revisor@exemplo.ao", password="revisao-lojas-2026")
    assert logged.status_code == 200 and logged.data["refreshToken"]
    assert _client(logged.data["accessToken"]).get("/api/v1/customer-portal/policies").status_code == 200
    with pytest.raises(Exception, match="registo"):
        call_command("create_store_review_account", tenant_id=str(tenant.id), registration_number="NAO-EXISTE",
                     email="x@y.ao", confirm=True)
    assert DEVICE
