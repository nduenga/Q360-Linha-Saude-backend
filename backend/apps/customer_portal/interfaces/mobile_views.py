"""Rotas da app móvel do Portal Cliente (roadmap_mobile.md, Fase 1). Todas
aditivas: o portal web não as usa.

Públicas (sem token): descobrir a seguradora, marca, renovar e terminar sessão.
Com token do portal: dispositivos ligados, dispositivos de push e preferências.
"""
from __future__ import annotations

import uuid

from django.http import Http404, HttpResponse
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.customer_portal.application import branding_service, device_session_service, discovery_service, push_service
from apps.customer_portal.domain.errors import PortalResourceNotFoundError
from apps.customer_portal.interfaces.portal_views import _PortalView
from apps.customer_portal.interfaces.rate_limit import is_device_rate_limited, is_discover_rate_limited
from apps.customer_portal.interfaces.serializers import (
    DiscoverSerializer,
    LogoutSerializer,
    PushDeviceRegisterSerializer,
    PushPreferencesUpdateSerializer,
    RefreshSerializer,
)
from apps.customer_portal.interfaces.views import (
    _bind_anonymous_customer_actor,
    _PublicAuthView,
    _remote_addr,
    _too_many_requests,
    session_response,
)
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.infrastructure.models import Tenant
from apps.foundation.interfaces.middleware import get_correlation_id
from apps.platform_admin.application.tenant_settings import logo_bytes


def _insurer_payload(request, branding: dict) -> dict:
    """Marca para a app: o logótipo vai como URL absoluto (a app só o descarrega)."""
    data = dict(branding)
    has_logo = data.pop("hasLogo", False)
    data["logoUrl"] = (
        request.build_absolute_uri(
            reverse("customer-portal-branding-logo", kwargs={"tenant_id": uuid.UUID(data["tenantId"])})
        )
        if has_logo
        else None
    )
    return data


# --------------------------------------------------------------- públicas
class DiscoverInsurerView(_PublicAuthView):
    """Passo 1 da app: «em que seguradora tenho conta?». Ver as notas de
    privacidade em `discovery_service`."""

    def post(self, request):
        body = DiscoverSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        email = body.validated_data["email"]
        if is_discover_rate_limited(remote_addr=_remote_addr(request), email=email):
            return _too_many_requests()
        insurers = [_insurer_payload(request, item) for item in discovery_service.discover(email)]
        return Response({"insurers": insurers}, status=200)


class InsurerBrandingView(_PublicAuthView):
    def get(self, request, tenant_id):
        branding = branding_service.get_branding(tenant_id)
        if branding is None:
            raise Http404()
        response = Response(_insurer_payload(request, branding), status=200)
        response["Cache-Control"] = "public, max-age=300"
        return response


class InsurerBrandingLogoView(_PublicAuthView):
    def get(self, request, tenant_id):
        tenant = Tenant.objects.filter(id=tenant_id).first()
        logo = logo_bytes(tenant_id) if tenant and branding_service.portal_enabled(tenant) else None
        if logo is None:
            raise Http404()
        data, content_type = logo
        response = HttpResponse(data, content_type=content_type)
        response["Cache-Control"] = "public, max-age=3600"
        return response


class RefreshSessionView(_PublicAuthView):
    """Troca o token de renovação por um par novo. O antigo deixa de servir: a
    app tem de guardar o novo antes de usar o de acesso e fazer um pedido de
    renovação de cada vez."""

    def post(self, request, tenant_id):
        body = RefreshSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        session_key = data["refreshToken"].partition(".")[0]
        if is_device_rate_limited(tenant_id=str(tenant_id), device_key=f"refresh:{session_key}"):
            return _too_many_requests()
        _bind_anonymous_customer_actor(tenant_id)
        session = device_session_service.refresh(
            data["refreshToken"], app_version=data.get("appVersion", ""), correlation_id=get_correlation_id()
        )
        return session_response(session)


class LogoutSessionView(_PublicAuthView):
    """Termina a sessão do dispositivo. Responde sempre 204 (nunca diz se o
    token era válido); com o token de acesso já expirado continua a funcionar."""

    def post(self, request, tenant_id):
        body = LogoutSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        _bind_anonymous_customer_actor(tenant_id)
        device_session_service.revoke_by_refresh_token(body.validated_data["refreshToken"])
        return Response(status=204)


# ------------------------------------------------------- com token do portal
class _MobilePortalView(_PortalView):
    @staticmethod
    def account_id() -> uuid.UUID:
        return uuid.UUID(CurrentActorProvider.get().actor_id)


class ConnectedSessionsView(_MobilePortalView):
    """«Dispositivos ligados» no perfil."""

    def get(self, request):
        sessions = device_session_service.list_sessions(
            self.account_id(), current_session_id=getattr(request, "portal_session_id", None)
        )
        return Response({"sessions": sessions})


class ConnectedSessionDetailView(_MobilePortalView):
    def delete(self, request, session_id):
        if not device_session_service.revoke_session(self.account_id(), session_id):
            raise PortalResourceNotFoundError("Sessão não encontrada")
        return Response(status=204)


class PushDevicesView(_MobilePortalView):
    def post(self, request):
        body = PushDeviceRegisterSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        try:
            device = push_service.register_device(
                account_id=self.account_id(), session_id=getattr(request, "portal_session_id", None),
                expo_token=data["expoToken"], platform=data["platform"],
            )
        except push_service.InvalidPushTokenError as exc:
            raise ValidationError({"expoToken": str(exc)}) from exc
        return Response({"id": str(device.id), "platform": device.platform, "active": device.active}, status=201)


class PushDeviceDetailView(_MobilePortalView):
    def delete(self, request, device_id):
        push_service.unregister_device(account_id=self.account_id(), device_id=device_id)
        return Response(status=204)


class PushPreferencesView(_MobilePortalView):
    def get(self, request):
        return Response({"preferences": push_service.get_preferences(self.account_id())})

    def put(self, request):
        body = PushPreferencesUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        changes = {item["category"]: item["enabled"] for item in body.validated_data["preferences"]}
        try:
            preferences = push_service.set_preferences(self.account_id(), changes)
        except ValueError as exc:
            raise ValidationError({"preferences": str(exc)}) from exc
        return Response({"preferences": preferences})
