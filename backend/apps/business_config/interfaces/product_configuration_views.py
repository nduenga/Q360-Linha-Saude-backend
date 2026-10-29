"""`/products/{id}/configuration` — a configuração do produto em cascata
seguradora → produto → plano: de onde vem cada valor em uso e a cópia da
configuração geral (ou de outro produto) para rascunhos do produto."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.business_config.application import product_configuration_service as service
from apps.business_config.domain.scope import PRODUCT_SCOPED_KEYS
from apps.business_config.interfaces.views import _ConfigPermissions
from apps.product.infrastructure.models import Product


class ProductConfigurationCopySerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=list(service.SOURCES), default=service.GENERAL)
    sourceProductId = serializers.UUIDField(required=False, allow_null=True, default=None)
    configKeys = serializers.ListField(
        child=serializers.ChoiceField(choices=list(PRODUCT_SCOPED_KEYS)), required=False, default=list)
    includePricingSetup = serializers.BooleanField(required=False, default=True)


class ProductConfigurationView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="getProductConfiguration",
                   summary="Configuração do produto: o que é do produto, o que herda da geral e o que fica sempre geral",
                   tags=["Configuration"])
    def get(self, request, product_id):
        return Response(service.describe_product_configuration(get_object_or_404(Product, id=product_id)))


class ProductConfigurationCopyView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="copyProductConfiguration",
                   summary="Criar rascunhos do produto a partir da configuração geral ou de outro produto",
                   tags=["Configuration"], request=ProductConfigurationCopySerializer)
    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        body = ProductConfigurationCopySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        source_product = get_object_or_404(Product, id=data["sourceProductId"]) if data["sourceProductId"] else None
        result = service.copy_configuration(
            product, source=data["source"], source_product=source_product, keys=data["configKeys"],
            include_pricing_setup=data["includePricingSetup"],
        )
        return Response(result, status=201)
