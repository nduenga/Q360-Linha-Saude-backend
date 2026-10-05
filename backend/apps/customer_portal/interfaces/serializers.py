"""DTOs for the customer portal's pre-auth endpoints. Not ART-006 (this
actor/contract does not exist there) — a new, small, portal-owned
contract per ROADMAP_PORTAL_CLIENTE.md Fase 0."""
from __future__ import annotations

from rest_framework import serializers


class RequestAccessSerializer(serializers.Serializer):
    policyNumber = serializers.CharField(max_length=100)
    registrationNumber = serializers.CharField(max_length=100)
    email = serializers.EmailField(max_length=320)


class VerifyOtpSerializer(serializers.Serializer):
    policyNumber = serializers.CharField(max_length=100)
    registrationNumber = serializers.CharField(max_length=100)
    email = serializers.EmailField(max_length=320)
    otp = serializers.CharField(min_length=6, max_length=6)


class PortalTokenResponseSerializer(serializers.Serializer):
    accessToken = serializers.CharField()
    tokenType = serializers.CharField(default="Bearer")
    expiresIn = serializers.IntegerField()


class FirstAccessRequestSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100, help_text="Número da apólice ou da cotação.")
    registrationNumber = serializers.CharField(max_length=100)


class FirstAccessMaskedEmailSerializer(serializers.Serializer):
    maskedEmail = serializers.CharField(help_text="Email para onde foi enviado o código, mascarado (jo***@gmail.com).")


class FirstAccessConfirmSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100)
    registrationNumber = serializers.CharField(max_length=100)
    otp = serializers.CharField(min_length=6, max_length=6)
    password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)


class PasswordLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=320)
    password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=320)


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=320)
    otp = serializers.CharField(min_length=6, max_length=6)
    password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)
