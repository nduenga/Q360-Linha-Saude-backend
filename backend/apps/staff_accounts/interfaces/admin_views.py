"""Admin-only staff account management - backs the Administration screen's
account management UI. Authentication is the default
`JwtActorAuthentication` (these are ordinary staff endpoints, just gated to
ADMIN by `IsAdminRole` instead of a DOC-001 s18 permission - see that
module's docstring for why).
"""
from __future__ import annotations

import uuid

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.staff_accounts.application import account_service
from apps.staff_accounts.interfaces.permissions import IsAdminRole
from apps.staff_accounts.interfaces.serializers import (
    CreateStaffAccountRequestSerializer,
    GeneratedPasswordSerializer,
    SetStatusRequestSerializer,
    StaffAccountSerializer,
    UpdateRolesRequestSerializer,
    account_view_to_dict,
)


class StaffAccountListCreateView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        accounts = account_service.list_accounts()
        return Response(StaffAccountSerializer([account_view_to_dict(a) for a in accounts], many=True).data)

    def post(self, request):
        body = CreateStaffAccountRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        view, generated_password = account_service.create_account(
            email=data["email"], name=data["name"], roles=data["roles"], password=data["password"]
        )
        payload = account_view_to_dict(view)
        if generated_password:
            payload["temporaryPassword"] = generated_password
        return Response(payload, status=201)


class StaffAccountRolesView(APIView):
    permission_classes = [IsAdminRole]

    def patch(self, request, account_id):
        body = UpdateRolesRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        view = account_service.update_roles(account_id=account_id, roles=body.validated_data["roles"])
        return Response(account_view_to_dict(view))


class StaffAccountStatusView(APIView):
    permission_classes = [IsAdminRole]

    def patch(self, request, account_id):
        body = SetStatusRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        view = account_service.set_status(account_id=account_id, status=body.validated_data["status"])
        return Response(account_view_to_dict(view))


class StaffAccountResetPasswordView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, account_id):
        new_password = account_service.reset_password(account_id=account_id)
        return Response(GeneratedPasswordSerializer({"temporaryPassword": new_password}).data)


class StaffAccountUnlockView(APIView):
    """POST /admin/staff-accounts/{id}/unlock — levanta o bloqueio por tentativas falhadas."""

    permission_classes = [IsAdminRole]

    def post(self, request, account_id):
        account_service.unlock(account_id=account_id)
        return Response(status=204)
