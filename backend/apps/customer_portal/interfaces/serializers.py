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


class DeviceSerializer(serializers.Serializer):
    """Dispositivo da app móvel. Quem o envia (a app) recebe também um token de
    renovação; a web não o envia e continua só com o token de acesso."""

    deviceId = serializers.CharField(max_length=100, help_text="Identificador estável da instalação da app.")
    deviceName = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    platform = serializers.ChoiceField(choices=["IOS", "ANDROID", "WEB", "OTHER"], required=False, default="OTHER")
    appVersion = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")


class PortalTokenResponseSerializer(serializers.Serializer):
    accessToken = serializers.CharField()
    tokenType = serializers.CharField(default="Bearer")
    expiresIn = serializers.IntegerField()
    refreshToken = serializers.CharField(required=False, help_text="Só quando o pedido trouxe `device` (app móvel).")
    refreshExpiresIn = serializers.IntegerField(required=False, help_text="Segundos até o token de renovação expirar sem uso.")


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
    device = DeviceSerializer(required=False)


class PasswordLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=320)
    password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)
    device = DeviceSerializer(required=False)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=320)


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=320)
    otp = serializers.CharField(min_length=6, max_length=6)
    password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)
    device = DeviceSerializer(required=False)


class DiscoverSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=320)


class RefreshSerializer(serializers.Serializer):
    refreshToken = serializers.CharField(max_length=200, trim_whitespace=False)
    appVersion = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")


class LogoutSerializer(serializers.Serializer):
    refreshToken = serializers.CharField(max_length=200, trim_whitespace=False)


class PushDeviceRegisterSerializer(serializers.Serializer):
    expoToken = serializers.CharField(max_length=200, help_text="ExponentPushToken[...] devolvido pelo expo-notifications.")
    platform = serializers.ChoiceField(choices=["IOS", "ANDROID", "WEB", "OTHER"], required=False, default="OTHER")


class PushPreferenceItemSerializer(serializers.Serializer):
    category = serializers.CharField(max_length=30)
    enabled = serializers.BooleanField()


class PushPreferencesUpdateSerializer(serializers.Serializer):
    preferences = PushPreferenceItemSerializer(many=True)
