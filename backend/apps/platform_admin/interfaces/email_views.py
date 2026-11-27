"""Servidor SMTP configurado no painel pela plataforma: o global e o de cada seguradora."""
from __future__ import annotations

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.infrastructure.models import Tenant
from apps.foundation.interfaces.middleware import get_correlation_id
from apps.platform_admin.application import email_settings
from apps.platform_admin.domain.errors import PlatformNotFoundError
from apps.platform_admin.interfaces.permissions import IsPlatformAdmin
from apps.platform_admin.interfaces.serializers import EmailSettingsInputSerializer, EmailTestRequestSerializer
from apps.staff_accounts.interfaces.rate_limit import is_recovery_rate_limited


def _actor_id(request) -> str:
    return request.user.actor.actor_id


def _tenant_id_or_404(tenant_id):
    if tenant_id is not None and not Tenant.objects.filter(id=tenant_id).exists():
        raise PlatformNotFoundError("Tenant não encontrado")
    return tenant_id


class _EmailSettingsBase(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, tenant_id=None):
        scope = _tenant_id_or_404(tenant_id)
        return Response(email_settings.to_dict(email_settings.get_row(scope), tenant_id=scope))

    def put(self, request, tenant_id=None):
        scope = _tenant_id_or_404(tenant_id)
        body = EmailSettingsInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        row = email_settings.save(tenant_id=scope, data=body.validated_data, actor_id=_actor_id(request),
                                  correlation_id=get_correlation_id())
        return Response(email_settings.to_dict(row, tenant_id=scope))

    def delete(self, request, tenant_id=None):
        scope = _tenant_id_or_404(tenant_id)
        email_settings.delete(tenant_id=scope, actor_id=_actor_id(request), correlation_id=get_correlation_id())
        return Response(status=204)


class PlatformEmailSettingsView(_EmailSettingsBase):
    """GET|PUT|DELETE /platform/email-settings: o servidor de email de toda a plataforma."""


class PlatformTenantEmailSettingsView(_EmailSettingsBase):
    """GET|PUT|DELETE /platform/tenants/{id}/email-settings: o servidor próprio de uma seguradora."""


class _EmailTestBase(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, tenant_id=None):
        scope = _tenant_id_or_404(tenant_id)
        body = EmailTestRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        if "to" not in body.validated_data:
            raise ValidationError({"to": "Indique o destinatário do teste."})
        if is_recovery_rate_limited(remote_addr=request.META.get("REMOTE_ADDR") or "unknown",
                                    email=f"smtp-test:{_actor_id(request)}"):
            return Response({"title": "Limite excedido", "status": 429, "code": "RATE-LIMIT",
                             "detail": "Demasiados testes de email. Tente de novo mais tarde."},
                            status=429, content_type="application/problem+json")
        return Response(email_settings.send_test(
            tenant_id=scope, to=body.validated_data["to"], actor_id=_actor_id(request),
            correlation_id=get_correlation_id()))


class PlatformEmailTestView(_EmailTestBase):
    """POST /platform/email-settings/test: envia uma mensagem real pelo servidor da plataforma."""


class PlatformTenantEmailTestView(_EmailTestBase):
    """POST /platform/tenants/{id}/email-settings/test: idem, pelo servidor da seguradora."""
