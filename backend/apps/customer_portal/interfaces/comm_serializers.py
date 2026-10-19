"""DTOs de entrada de pedidos, mensagens e notificações (PDF s.8, 14, 15) —
contrato próprio do portal, tal como o resto de `apps.customer_portal`."""
from __future__ import annotations

from rest_framework import serializers

from apps.customer_portal.domain import requests as rules


class CreateRequestSerializer(serializers.Serializer):
    requestType = serializers.ChoiceField(choices=sorted(rules.REQUEST_TYPES))
    subject = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    description = serializers.CharField(max_length=4000, required=False, allow_blank=True, default="")
    policyNumber = serializers.CharField(max_length=100, required=False, allow_null=True, default=None)
    quoteNumber = serializers.CharField(max_length=100, required=False, allow_null=True, default=None)
    payload = serializers.DictField(required=False, default=dict)


class MessageSerializer(serializers.Serializer):
    contextType = serializers.ChoiceField(choices=["QUOTE", "POLICY", "REQUEST"])
    contextRef = serializers.CharField(max_length=100)
    body = serializers.CharField(max_length=4000)


class MarkReadSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_null=True, default=None)


class TransitionSerializer(serializers.Serializer):
    toStatus = serializers.ChoiceField(choices=sorted(rules.STATUS_LABELS))
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, allow_null=True, default=None)


class RequestSatisfactionSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=0)
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
