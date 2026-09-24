"""DTOs for the self-hosted staff identity endpoints - not ART-006 (that
contract predates this app; same "pragmatic V1 addition" posture as
DevLoginView/dev-login), so field names follow ART-006's own camelCase
convention for consistency but this isn't a Change Request against it.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.foundation.domain.permissions import Role
from apps.staff_accounts.infrastructure.models import StaffAccount

_ROLE_CHOICES = [r.value for r in Role]
_STATUS_CHOICES = [StaffAccount.ACTIVE, StaffAccount.DISABLED]


class LoginRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=320)
    password = serializers.CharField(max_length=200)


class RefreshRequestSerializer(serializers.Serializer):
    refreshToken = serializers.CharField()


class LogoutRequestSerializer(serializers.Serializer):
    refreshToken = serializers.CharField()


class TokenResponseSerializer(serializers.Serializer):
    accessToken = serializers.CharField()
    refreshToken = serializers.CharField()
    expiresIn = serializers.IntegerField()
    accountId = serializers.CharField()
    name = serializers.CharField()
    email = serializers.EmailField()
    roles = serializers.ListField(child=serializers.CharField())


class StaffAccountSerializer(serializers.Serializer):
    id = serializers.CharField()
    email = serializers.EmailField()
    name = serializers.CharField()
    status = serializers.CharField()
    roles = serializers.ListField(child=serializers.CharField())
    lastLoginAt = serializers.DateTimeField(allow_null=True)


def account_view_to_dict(view) -> dict:
    return {
        "id": str(view.id),
        "email": view.email,
        "name": view.name,
        "status": view.status,
        "roles": view.roles,
        "lastLoginAt": view.last_login_at,
    }


class CreateStaffAccountRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=320)
    name = serializers.CharField(max_length=200)
    roles = serializers.ListField(child=serializers.ChoiceField(choices=_ROLE_CHOICES), allow_empty=False)
    # Omit to have the backend generate one (returned once in the response).
    password = serializers.CharField(max_length=200, required=False, allow_null=True, default=None)


class UpdateRolesRequestSerializer(serializers.Serializer):
    roles = serializers.ListField(child=serializers.ChoiceField(choices=_ROLE_CHOICES), allow_empty=False)


class SetStatusRequestSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=_STATUS_CHOICES)


class GeneratedPasswordSerializer(serializers.Serializer):
    temporaryPassword = serializers.CharField()
