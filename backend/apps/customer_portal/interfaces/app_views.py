"""Rotas da app móvel, fases 3 e 4 (roadmap_mobile.md): configuração da app,
rede convencionada, idioma, apagar conta, eventos de uso e, no backoffice, a
gestão dos prestadores e as métricas."""
from __future__ import annotations

from django.conf import settings
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customer_portal.application import account_service, providers_service, usage_service
from apps.customer_portal.interfaces.app_serializers import (
    CareProviderSerializer,
    DeleteAccountSerializer,
    PreferencesSerializer,
    UsageEventsSerializer,
)
from apps.customer_portal.interfaces.app_version import is_below_minimum
from apps.customer_portal.interfaces.mobile_views import _MobilePortalView
from apps.customer_portal.interfaces.rate_limit import is_device_rate_limited
from apps.customer_portal.interfaces.views import _PublicAuthView, _too_many_requests
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import get_correlation_id
from apps.foundation.interfaces.permissions import require_scope


# ------------------------------------------------------ app: configuração
class AppConfigView(_PublicAuthView):
    """Versão mínima/atual e lojas. Nunca é bloqueada pela versão mínima."""

    def get(self, request):
        version = request.headers.get("X-App-Version", "")
        minimum = settings.CUSTOMER_PORTAL_MIN_APP_VERSION
        return Response(
            {
                "minVersion": minimum or None,
                "latestVersion": settings.CUSTOMER_PORTAL_LATEST_APP_VERSION or None,
                "updateRequired": bool(minimum and version and is_below_minimum(version, minimum)),
                "storeUrls": {
                    "ios": settings.CUSTOMER_PORTAL_IOS_STORE_URL or None,
                    "android": settings.CUSTOMER_PORTAL_ANDROID_STORE_URL or None,
                },
            }
        )


# ------------------------------------------------------ rede convencionada
def _number(request, name):
    raw = request.query_params.get(name)
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ValidationError({name: "Tem de ser um número."}) from exc


class PortalProvidersView(_MobilePortalView):
    """Prestadores ativos da rede. Com `lat` e `lng` ordena pela distância."""

    def get(self, request):
        params = request.query_params
        provider_type = params.get("type", "")
        if provider_type and provider_type not in providers_service.TYPES:
            raise ValidationError({"type": f"Tem de ser um de {list(providers_service.TYPES)}."})
        lat, lng, radius = _number(request, "lat"), _number(request, "lng"), _number(request, "radiusKm")
        if (lat is None) != (lng is None):
            raise ValidationError({"lat": "Indique lat e lng juntos."})
        if lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValidationError({"lat": "Coordenadas fora do intervalo."})
        emergency = params.get("emergency")
        try:
            limit = int(params.get("limit", 50))
        except ValueError as exc:
            raise ValidationError({"limit": "Tem de ser um inteiro."}) from exc
        return Response(
            {
                "providers": providers_service.search(
                    q=params.get("q", ""), province=params.get("province", ""), provider_type=provider_type,
                    specialty=params.get("specialty", ""),
                    emergency=None if emergency is None else emergency.lower() == "true",
                    lat=lat, lng=lng, radius_km=radius, limit=limit,
                )
            }
        )


# -------------------------------------------- idioma, apagar conta, eventos
class PortalPreferencesView(_MobilePortalView):
    def get(self, request):
        return Response({"language": account_service.get_language(self.account_id())})

    def put(self, request):
        body = PreferencesSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response({"language": account_service.set_language(self.account_id(), body.validated_data["language"])})


class PortalAccountView(_MobilePortalView):
    """Apagar a conta dentro da app (exigência da Apple); pede a palavra-passe."""

    def delete(self, request):
        body = DeleteAccountSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        tenant_id = str(CurrentActorProvider.get().tenant_id.value)
        if is_device_rate_limited(tenant_id=tenant_id, device_key=f"delete:{self.account_id()}"):
            return _too_many_requests()
        account_service.delete_account(
            self.account_id(), password=body.validated_data["password"], correlation_id=get_correlation_id()
        )
        return Response(status=204)


class PortalUsageEventsView(_MobilePortalView):
    def post(self, request):
        body = UsageEventsSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        accepted = usage_service.record(
            account_id=self.account_id(), events=data["events"], platform=data["platform"],
            app_version=data["appVersion"] or request.headers.get("X-App-Version", ""),
        )
        return Response({"accepted": accepted}, status=202)


# ---------------------------------------------------------- backoffice
class StaffCareProvidersView(APIView):
    """GET lê (Scope.READ); POST cria (Scope.WRITE, verificado em `get_permissions`)."""

    def get_permissions(self):
        scope = Scope.WRITE if self.request.method == "POST" else Scope.READ
        return [require_scope(scope)()]

    def get(self, request):
        return Response({"providers": providers_service.search(limit=100, include_inactive=True)})

    def post(self, request):
        body = CareProviderSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        created = providers_service.create(
            tenant_id=CurrentActorProvider.get().tenant_id.value, data=body.validated_data
        )
        return Response(created, status=201)


class StaffCareProviderDetailView(APIView):
    permission_classes = [require_scope(Scope.WRITE)]

    def put(self, request, provider_id):
        body = CareProviderSerializer(data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        return Response(providers_service.update(provider_id, body.validated_data))

    def delete(self, request, provider_id):
        providers_service.deactivate(provider_id)
        return Response(status=204)


class PortalAppMetricsView(APIView):
    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        try:
            days = int(request.query_params.get("days", 30))
        except ValueError as exc:
            raise ValidationError({"days": "Tem de ser um inteiro."}) from exc
        return Response(usage_service.metrics(days=max(1, min(days, 365))))
