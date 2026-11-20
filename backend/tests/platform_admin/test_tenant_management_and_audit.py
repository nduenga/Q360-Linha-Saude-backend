"""Gestão das seguradoras pela plataforma (saúde, arranque, suspensão com
aviso, identidade visual, limites e módulos) e auditoria (pesquisa,
antes/depois, exportação, alertas e registo dos acessos)."""
from __future__ import annotations

import base64
import datetime

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.foundation.infrastructure.models import Tenant
from apps.platform_admin.infrastructure.models import PlatformAuditEvent
from apps.staff_accounts.infrastructure.models import StaffAccount
from tests.platform_admin.test_platform_admin import _admin, _client, _keys  # noqa: F401  (fixture)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _new_tenant(client, name="Seguradora Gestão", admin_email="admin@gestao.ao"):
    created = client.post("/api/v1/platform/tenants", {
        "name": name, "profile": {"nif": "5417000099", "email": "geral@gestao.ao"},
        "admin": {"name": "Admin Gestão", "email": admin_email},
    }, format="json")
    assert created.status_code == 201, created.content
    return created.data["tenant"]


@pytest.mark.django_db
def test_health_panel_and_onboarding_checklist():
    _admin()
    client = _client()
    tenant = _new_tenant(client)
    health = client.get(f"/api/v1/platform/tenants/{tenant['id']}/health")
    assert health.status_code == 200, health.content
    data = health.data
    assert data["activeUsers"] == 1 and data["lastLoginAt"] is None
    assert data["quotesThisMonth"] == 0 and data["policiesThisMonth"] == 0
    steps = {s["key"]: s["status"] for s in data["onboarding"]["steps"]}
    assert steps["company"] == "DONE" and steps["firstAdmin"] == "WARNING" and steps["tariff"] == "PENDING"
    assert "Tarifa publicada" in data["missingConfiguration"]
    # consultar a seguradora fica registado
    assert PlatformAuditEvent.objects.filter(action="platform.tenant_viewed", tenant_id=tenant["id"]).exists()


@pytest.mark.django_db
def test_suspension_needs_a_reason_notifies_admins_and_reactivates_on_the_date(django_capture_on_commit_callbacks):
    _admin()
    client = _client()
    tenant = _new_tenant(client)
    url = f"/api/v1/platform/tenants/{tenant['id']}"
    assert client.patch(url, {"status": "SUSPENDED"}, format="json").status_code == 409
    mail.outbox.clear()
    until = (timezone.localdate() + datetime.timedelta(days=3)).isoformat()
    with django_capture_on_commit_callbacks(execute=True):
        suspended = client.patch(url, {"status": "SUSPENDED", "suspensionReason": "Falta de pagamento da subscrição",
                                       "reactivateOn": until}, format="json")
    assert suspended.status_code == 200, suspended.content
    assert suspended.data["settings"]["suspension"]["reason"] == "Falta de pagamento da subscrição"
    assert mail.outbox[-1].to == ["admin@gestao.ao"] and "Falta de pagamento" in mail.outbox[-1].body

    from apps.platform_admin.application.tenant_service import reactivate_due_tenants

    assert reactivate_due_tenants(today=timezone.localdate()) == []
    with django_capture_on_commit_callbacks(execute=True):
        assert reactivate_due_tenants(today=timezone.localdate() + datetime.timedelta(days=3)) == [tenant["code"]]
    assert Tenant.objects.get(id=tenant["id"]).status == "ACTIVE"
    assert "reativado" in mail.outbox[-1].subject
    event = PlatformAuditEvent.objects.filter(action="platform.tenant_status_changed", tenant_id=tenant["id"]) \
        .order_by("occurred_at").first()
    assert event.metadata_json["before"]["status"] == "ACTIVE" and event.metadata_json["after"]["status"] == "SUSPENDED"


@pytest.mark.django_db
def test_branding_logo_limits_and_modules():
    _admin()
    client = _client()
    tenant = _new_tenant(client)
    base = f"/api/v1/platform/tenants/{tenant['id']}"
    bad = client.patch(f"{base}/settings", {"branding": {"primaryColor": "azul"}}, format="json")
    assert bad.status_code == 409
    saved = client.patch(f"{base}/settings", {"branding": {"primaryColor": "#0b3d91"},
                                              "limits": {"maxUsers": 1, "modules": {"customerPortal": False}}},
                         format="json")
    assert saved.status_code == 200, saved.content
    assert saved.data["settings"]["branding"]["primaryColor"] == "#0B3D91"
    assert saved.data["settings"]["limits"]["maxUsers"] == 1
    assert saved.data["settings"]["limits"]["modules"]["customerPortal"] is False

    logo = client.post(f"{base}/logo", {"file": SimpleUploadedFile("logo.png", PNG, content_type="image/png")},
                       format="multipart")
    assert logo.status_code == 200, logo.content
    assert logo.data["settings"]["branding"]["hasLogo"] is True
    assert client.get(f"{base}/logo").content == PNG

    # limite de utilizadores: já tem 1 administrador ativo
    blocked = client.post(f"{base}/admins", {"name": "Outro", "email": "outro@gestao.ao"}, format="json")
    assert blocked.status_code == 409 and "máximo" in blocked.data["detail"]

    # Portal do Cliente desligado: os pedidos públicos do portal deixam de funcionar
    from rest_framework.test import APIClient

    refused = APIClient().post(f"/api/v1/customer-portal/{tenant['id']}/auth/password-reset/request",
                               {"email": "x@y.ao"}, format="json")
    assert refused.status_code == 404 and refused.data["code"] == "PORTAL-DISABLED"

    # antes/depois na auditoria
    page = client.get("/api/v1/platform/audit/search", {"tenantId": tenant["id"], "action": "settings"}).data
    changes = {c["field"]: (c["before"], c["after"]) for c in page["items"][0]["changes"]}
    assert changes["limits.maxUsers"] == (None, 1) and changes["branding.primaryColor"] == (None, "#0B3D91")


@pytest.mark.django_db
def test_tenant_branding_is_used_when_the_insurer_has_not_published_its_own():
    _admin()
    client = _client()
    tenant = _new_tenant(client)
    client.patch(f"/api/v1/platform/tenants/{tenant['id']}/settings", {"branding": {"primaryColor": "#112233"}},
                 format="json")
    from apps.business_config.application.branding import branding_from
    from apps.business_config.application.readers import BusinessSnapshot
    from apps.foundation.application.context import CurrentActorProvider
    from apps.foundation.domain.actor import Actor
    from apps.foundation.domain.tenant import TenantId

    token = CurrentActorProvider.bind(Actor(actor_id="t", tenant_id=TenantId.parse(tenant["id"]), roles=frozenset()))
    try:
        branding = branding_from(BusinessSnapshot.load())
    finally:
        CurrentActorProvider.reset(token)
    assert branding["company"] == "Seguradora Gestão" and branding["color"] == "#112233"


@pytest.mark.django_db
def test_audit_search_filters_export_and_alerts():
    _admin()
    client = _client()
    tenant = _new_tenant(client)
    today = timezone.localdate().isoformat()
    page = client.get("/api/v1/platform/audit/search",
                      {"source": "PLATFORM", "tenantId": tenant["id"], "dateFrom": today, "dateTo": today, "size": 5})
    assert page.status_code == 200 and page.data["total"] >= 1
    assert all(item["tenantId"] == str(tenant["id"]) for item in page.data["items"])
    assert page.data["items"][0]["tenantName"] == "Seguradora Gestão"
    old = client.get("/api/v1/platform/audit/search", {"dateTo": "2000-01-01"}).data
    assert old["total"] == 0

    xlsx = client.get("/api/v1/platform/audit/export", {"fileType": "xlsx", "tenantId": tenant["id"]})
    assert xlsx.status_code == 200 and xlsx.content.startswith(b"PK")
    pdf = client.get("/api/v1/platform/audit/export", {"fileType": "pdf"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert PlatformAuditEvent.objects.filter(action="platform.audit_exported").count() == 2

    account = StaffAccount.all_tenants.get(email="admin@gestao.ao")
    StaffAccount.all_tenants.filter(id=account.id).update(locked_until=timezone.now() + datetime.timedelta(minutes=10))
    for _ in range(3):
        PlatformAuditEvent.objects.create(actor_id="ANONYMOUS", action="platform.login_failed",
                                          entity_type="PlatformAdmin", entity_id=None)
    kinds = {a["kind"] for a in client.get("/api/v1/platform/alerts").data}
    assert {"LOCKED_ACCOUNT", "FAILED_LOGINS"} <= kinds
