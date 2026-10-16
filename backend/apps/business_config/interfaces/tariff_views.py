"""`/products/{id}/tariff` — a tarifa de um produto por passo (ordem do
motor, estado das versões, dono de cada passo) e a simulação de rascunhos
antes de os submeter. A simulação não grava nada."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.business_config.application import tariff_service
from apps.business_config.interfaces.views import _ConfigPermissions
from apps.product.infrastructure.models import Product


class TariffMemberSerializer(serializers.Serializer):
    age = serializers.IntegerField(min_value=0, max_value=120)
    sex = serializers.ChoiceField(choices=["M", "F"], default="M")
    relationship = serializers.CharField(required=False, allow_null=True, default=None, max_length=40)


class TariffSimulationSerializer(serializers.Serializer):
    planId = serializers.UUIDField()
    members = TariffMemberSerializer(many=True)
    proposerType = serializers.ChoiceField(choices=["INDIVIDUAL", "ORGANISATION"], default="INDIVIDUAL")
    selection = serializers.JSONField(required=False, default=None)
    actuarialProfile = serializers.JSONField(required=False, default=None)
    paymentFrequency = serializers.ChoiceField(choices=list(tariff_service.FREQUENCIES), required=False, default=None)
    configurationIds = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    includeOpenDrafts = serializers.BooleanField(required=False, default=False)


class ProductTariffView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="getProductTariff", summary="Tarifa do produto por passo do cálculo",
                   tags=["Configuration"])
    def get(self, request, product_id):
        return Response(tariff_service.describe_tariff(get_object_or_404(Product, id=product_id)))


class ProductTariffSimulationView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="simulateProductTariff",
                   summary="Simular a tarifa (com rascunhos) numa cotação de exemplo, sem gravar nada",
                   tags=["Configuration"], request=TariffSimulationSerializer)
    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        body = TariffSimulationSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        return Response(tariff_service.simulate_tariff(
            product, plan_id=data["planId"], members=[dict(m) for m in data["members"]],
            proposer_type=data["proposerType"], selection=data["selection"],
            actuarial_profile=data["actuarialProfile"], payment_frequency=data["paymentFrequency"],
            configuration_ids=[str(c) for c in data["configurationIds"]],
            include_open_drafts=data["includeOpenDrafts"],
        ))
