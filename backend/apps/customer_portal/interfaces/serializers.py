"""DTOs for the customer portal's pre-auth endpoints. Not ART-006 (this
actor/contract does not exist there) — a new, small, portal-owned
contract per ROADMAP_PORTAL_CLIENTE.md Fase 0."""
from __future__ import annotations

from rest_framework import serializers


class RequestAccessSerializer(serializers.Serializer):
    quoteNumber = serializers.CharField(max_length=100)
    registrationNumber = serializers.CharField(max_length=100)
    email = serializers.EmailField(max_length=320)


class VerifyOtpSerializer(serializers.Serializer):
    quoteNumber = serializers.CharField(max_length=100)
    registrationNumber = serializers.CharField(max_length=100)
    email = serializers.EmailField(max_length=320)
    otp = serializers.CharField(min_length=6, max_length=6)


class PortalTokenResponseSerializer(serializers.Serializer):
    accessToken = serializers.CharField()
    tokenType = serializers.CharField(default="Bearer")
    expiresIn = serializers.IntegerField()
