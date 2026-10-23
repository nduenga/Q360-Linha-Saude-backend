"""API de plataforma (super administradores): autenticação própria, tenants,
super admins e auditoria. Só aceita tokens `token_type=platform`."""
import uuid

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.interfaces.middleware import get_correlation_id, requires_idempotency
from apps.platform_admin.application import admin_service, auth_service, tenant_service
from apps.platform_admin.infrastructure.models import PlatformAdmin, PlatformAuditEvent
from apps.platform_admin.interfaces.permissions import IsPlatformAdmin
from apps.platform_admin.interfaces.serializers import (
    ChangePasswordSerializer,
    CreatePlatformAdminSerializer,
    CreateTenantSerializer,
    PlatformLoginSerializer,
    UpdatePlatformAdminStatusSerializer,
    UpdateTenantSerializer,
)

NOTICE = "Esta palavra-passe é mostrada uma única vez. Guarde-a em segurança e peça ao utilizador que a altere."


def _tenant(t) -> dict:
    return {"id": t.id, "code": t.code, "name": t.name, "status": t.status, "profile": t.profile_json or {},
            "createdAt": t.created_at, "updatedAt": t.updated_at}


def _admin(a) -> dict:
    return {"id": a.id, "email": a.email, "name": a.name, "status": a.status, "lastLoginAt": a.last_login_at,
            "createdAt": a.created_at}


def _actor_id(request) -> str:
    return request.user.actor.actor_id


class PlatformLoginView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        body = PlatformLoginSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        token, expires, account = auth_service.login(
            email=body.validated_data["email"], password=body.validated_data["password"],
            correlation_id=get_correlation_id(),
        )
        return Response({"accessToken": token, "expiresIn": expires, "adminId": account.id,
                         "name": account.name, "email": account.email})


class PlatformMeView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        return Response(_admin(admin_service.get_admin(_actor_id(request))))


@requires_idempotency
class PlatformChangePasswordView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request):
        body = ChangePasswordSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        admin_service.change_own_password(
            admin_id=_actor_id(request), current=body.validated_data["currentPassword"],
            new=body.validated_data["newPassword"], correlation_id=get_correlation_id(),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@requires_idempotency
class PlatformTenantListCreateView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        tenants = tenant_service.list_tenants(
            actor_id=_actor_id(request), correlation_id=get_correlation_id(),
            status=request.query_params.get("status"), search=request.query_params.get("q"),
        )
        return Response([_tenant(t) for t in tenants])

    def post(self, request):
        body = CreateTenantSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        d = body.validated_data
        tenant, admin, password = tenant_service.create_tenant(
            actor_id=_actor_id(request), code=d["code"].lower(), name=d["name"].strip(), profile=d.get("profile"),
            admin_email=d["admin"]["email"].lower(), admin_name=d["admin"]["name"].strip(),
            correlation_id=get_correlation_id(),
        )
        return Response(
            {"tenant": _tenant(tenant), "admin": {"id": admin.id, "email": admin.email, "name": admin.name, "role": "ADMIN"},
             "temporaryPassword": password, "temporaryPasswordNotice": NOTICE},
            status=status.HTTP_201_CREATED,
        )


@requires_idempotency
class PlatformTenantDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request, tenant_id):
        tenant, accounts, stats = tenant_service.tenant_detail(tenant_id=tenant_id)
        return Response({
            "tenant": _tenant(tenant),
            "accounts": [{"id": a.id, "email": a.email, "name": a.name, "status": a.status,
                          "roles": a.roles_list, "lastLoginAt": a.last_login_at} for a in accounts],
            "stats": stats,
        })

    def patch(self, request, tenant_id):
        body = UpdateTenantSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        d = body.validated_data
        tenant = tenant_service.update_tenant(
            actor_id=_actor_id(request), tenant_id=tenant_id, name=d.get("name"), profile=d.get("profile"),
            status=d.get("status"), correlation_id=get_correlation_id(),
        )
        return Response(_tenant(tenant))


@requires_idempotency
class PlatformTenantAdminsView(APIView):
    """POST adds another ADMIN to the tenant (temporary password shown once)."""

    permission_classes = [IsPlatformAdmin]

    def post(self, request, tenant_id):
        body = CreatePlatformAdminSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        admin, password = tenant_service.add_tenant_admin(
            actor_id=_actor_id(request), tenant_id=tenant_id, email=body.validated_data["email"].lower(),
            name=body.validated_data["name"].strip(), correlation_id=get_correlation_id(),
        )
        return Response({"accountId": admin.id, "email": admin.email, "temporaryPassword": password,
                         "temporaryPasswordNotice": NOTICE}, status=status.HTTP_201_CREATED)


@requires_idempotency
class PlatformTenantAccountResetView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, tenant_id, account_id):
        account, password = tenant_service.reset_tenant_account_password(
            actor_id=_actor_id(request), tenant_id=tenant_id, account_id=account_id,
            correlation_id=get_correlation_id(),
        )
        return Response({"accountId": account.id, "email": account.email, "temporaryPassword": password,
                         "temporaryPasswordNotice": NOTICE})


@requires_idempotency
class PlatformAdminListCreateView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        return Response([_admin(a) for a in admin_service.list_admins()])

    def post(self, request):
        body = CreatePlatformAdminSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        admin, password = admin_service.create_admin(
            actor_id=_actor_id(request), email=body.validated_data["email"], name=body.validated_data["name"],
            correlation_id=get_correlation_id(),
        )
        return Response({"admin": _admin(admin), "temporaryPassword": password, "temporaryPasswordNotice": NOTICE},
                        status=status.HTTP_201_CREATED)


@requires_idempotency
class PlatformAdminStatusView(APIView):
    permission_classes = [IsPlatformAdmin]

    def patch(self, request, admin_id):
        body = UpdatePlatformAdminStatusSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        admin = admin_service.set_status(
            actor_id=_actor_id(request), admin_id=admin_id, status=body.validated_data["status"],
            correlation_id=get_correlation_id(),
        )
        return Response(_admin(admin))


@requires_idempotency
class PlatformAdminResetPasswordView(APIView):
    permission_classes = [IsPlatformAdmin]

    def post(self, request, admin_id):
        admin, password = admin_service.reset_password(
            actor_id=_actor_id(request), admin_id=admin_id, correlation_id=get_correlation_id()
        )
        return Response({"accountId": admin.id, "email": admin.email, "temporaryPassword": password,
                         "temporaryPasswordNotice": NOTICE})


class PlatformAuditView(APIView):
    """GET /platform/audit?action=&entityType=&entityId=&actorId=&limit= (newest first)."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = PlatformAuditEvent.objects.order_by("-occurred_at")
        for param, column in (("action", "action"), ("entityType", "entity_type"),
                              ("entityId", "entity_id"), ("actorId", "actor_id")):
            if request.query_params.get(param):
                qs = qs.filter(**{column: request.query_params[param]})
        try:
            limit = max(1, min(int(request.query_params.get("limit", 100)), 500))
        except ValueError:
            limit = 100
        events = list(qs[:limit])
        actor_ids = []
        for e in events:
            try:
                actor_ids.append(uuid.UUID(str(e.actor_id)))
            except (TypeError, ValueError):
                continue
        # actor_id aqui é quase sempre o id de um PlatformAdmin — mostrar o
        # UUID cru na auditoria do super admin não diz a quem o leia quem
        # fez a ação; "ANONYMOUS" (login falhado antes de autenticar) não é
        # um UUID e fica sem nome, o que é o esperado.
        actor_names = {
            str(row["id"]): row["name"]
            for row in PlatformAdmin.objects.filter(id__in=actor_ids).values("id", "name")
        }
        return Response([
            {"id": e.id, "actorId": e.actor_id, "actorName": actor_names.get(str(e.actor_id)),
             "action": e.action, "entityType": e.entity_type,
             "entityId": e.entity_id, "occurredAt": e.occurred_at, "correlationId": e.correlation_id,
             "metadata": e.metadata_json}
            for e in events
        ])
