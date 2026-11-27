"""O administrador da seguradora configura o servidor de email da sua seguradora."""
from __future__ import annotations

from django.core.exceptions import ValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.interfaces.middleware import get_correlation_id
from apps.platform_admin.application import email_settings
from apps.platform_admin.interfaces.serializers import EmailSettingsInputSerializer
from apps.staff_accounts.infrastructure.models import StaffAccount
from apps.staff_accounts.interfaces.permissions import IsAdminRole
from apps.staff_accounts.interfaces.rate_limit import is_recovery_rate_limited


def _ctx(request):
    actor = request.user.actor
    return actor.tenant_id.value, str(actor.actor_id)


class TenantEmailSettingsView(APIView):
    """GET|PUT|DELETE /admin/email-settings. Sem configuração própria usa a da plataforma (`inheritedFrom`)."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        tenant_id, _ = _ctx(request)
        return Response(email_settings.to_dict(email_settings.get_row(tenant_id), tenant_id=tenant_id))

    def put(self, request):
        tenant_id, actor_id = _ctx(request)
        body = EmailSettingsInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        row = email_settings.save(tenant_id=tenant_id, data=body.validated_data, actor_id=actor_id,
                                  correlation_id=get_correlation_id())
        return Response(email_settings.to_dict(row, tenant_id=tenant_id))

    def delete(self, request):
        tenant_id, actor_id = _ctx(request)
        email_settings.delete(tenant_id=tenant_id, actor_id=actor_id, correlation_id=get_correlation_id())
        return Response(status=204)


class TenantEmailTestView(APIView):
    """POST /admin/email-settings/test: envia uma mensagem real para o email do próprio administrador."""

    permission_classes = [IsAdminRole]

    def post(self, request):
        tenant_id, actor_id = _ctx(request)
        if is_recovery_rate_limited(remote_addr=request.META.get("REMOTE_ADDR") or "unknown",
                                    email=f"smtp-test:{actor_id}"):
            return Response({"title": "Limite excedido", "status": 429, "code": "RATE-LIMIT",
                             "detail": "Demasiados testes de email. Tente de novo mais tarde."},
                            status=429, content_type="application/problem+json")
        try:
            account = StaffAccount.objects.filter(id=actor_id).first()
        except (ValueError, ValidationError):
            account = None
        if account is None:
            raise DRFValidationError({"detail": "Esta sessão não tem uma conta de utilizador para receber o teste."})
        return Response(email_settings.send_test(tenant_id=tenant_id, to=account.email, actor_id=actor_id,
                                                 correlation_id=get_correlation_id()))
