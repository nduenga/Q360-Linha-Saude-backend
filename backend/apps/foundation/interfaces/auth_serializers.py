from __future__ import annotations

from rest_framework import serializers


class DevLoginRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class DevLoginResponseSerializer(serializers.Serializer):
    accessToken = serializers.CharField()
    expiresIn = serializers.IntegerField()
    name = serializers.CharField()
