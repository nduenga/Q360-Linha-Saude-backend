"""DTOs das rotas da app móvel, fases 3 e 4 (roadmap_mobile.md)."""
from __future__ import annotations

from rest_framework import serializers


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)


class PreferencesSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=["pt", "en"])


class UsageEventSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=40)
    screen = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")


class UsageEventsSerializer(serializers.Serializer):
    events = UsageEventSerializer(many=True, allow_empty=False, max_length=50)
    appVersion = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    platform = serializers.ChoiceField(choices=["IOS", "ANDROID", "WEB", "OTHER"], required=False, default="OTHER")


class CareProviderSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    type = serializers.ChoiceField(
        choices=["HOSPITAL", "CLINIC", "LAB", "PHARMACY", "IMAGING", "DENTAL", "OTHER"], default="CLINIC"
    )
    specialties = serializers.ListField(child=serializers.CharField(max_length=80), required=False, default=list)
    province = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    municipality = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    address = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    openingHours = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    emergency = serializers.BooleanField(required=False, default=False)
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True, min_value=-90, max_value=90
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True, min_value=-180, max_value=180
    )
    active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        if not self.partial and (attrs.get("latitude") is None) != (attrs.get("longitude") is None):
            raise serializers.ValidationError("Indique a latitude e a longitude juntas, ou nenhuma.")
        return attrs
