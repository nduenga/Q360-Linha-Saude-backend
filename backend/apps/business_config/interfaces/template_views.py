"""`/templates` — modelos de partida do fornecedor vistos pelo tenant: a
versão publicada de cada modelo e a adoção (cópia para rascunhos)."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.business_config.application import platform_templates
from apps.business_config.interfaces.views import _ConfigPermissions


class TemplateAdoptSerializer(serializers.Serializer):
    effectiveFrom = serializers.DateField(required=False, allow_null=True, default=None)


class TemplateListView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="listTemplates", summary="Modelos de partida publicados pelo fornecedor",
                   tags=["Configuration"])
    def get(self, request):
        return Response(platform_templates.list_published())


class TemplateDetailView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="getTemplate", summary="Conteúdo da versão publicada de um modelo",
                   tags=["Configuration"])
    def get(self, request, code):
        return Response(platform_templates.describe(code, published_only=True))


class TemplateAdoptView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="adoptTemplate",
                   summary="Copiar um modelo para rascunhos do tenant (não publica nada)",
                   tags=["Configuration"], request=TemplateAdoptSerializer)
    def post(self, request, code):
        body = TemplateAdoptSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(platform_templates.adopt(request, code=code, effective_from=body.validated_data["effectiveFrom"]),
                        status=201)
