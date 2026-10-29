"""API de gestão de fórmulas (`pricing.formulas`).

Cada versão do conjunto de fórmulas é uma `BusinessConfiguration` com o
ciclo de vida comum (DRAFT -> PENDING_APPROVAL -> PUBLISHED; a rejeição
deixa-a REJECTED, que volta a DRAFT ao ser editada; RETIRED). Estas rotas são
uma fachada dedicada para o editor de fórmulas: acrescentam o catálogo, a
análise de dependências e a simulação.
"""
from __future__ import annotations

import uuid

from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.business_config.application.service import (
    approve_configuration,
    configuration_history,
    create_configuration,
    reject_configuration,
    retire_configuration,
    submit_configuration,
    update_configuration,
)
from apps.business_config.application.formula_variables import variable_catalog
from apps.business_config.domain.errors import InvalidConfiguration
from apps.business_config.domain.scope import SEPARATOR, product_key, valid_product_id
from apps.business_config.domain.formula_engine import FormulaError, explain_formula, referenced_names
from apps.business_config.domain.formulas import (
    CONFIG_KEY,
    evaluate_formula_set,
    formula_catalog,
    parse_formula_set,
)
from apps.business_config.infrastructure.models import BusinessConfiguration
from apps.business_config.interfaces.serializers import (
    BusinessConfigurationHistorySerializer,
    BusinessConfigurationRejectSerializer,
    BusinessConfigurationSerializer,
    BusinessConfigurationUpdateSerializer,
    FormulaSimulateSerializer,
    FormulaSubmitSerializer,
    FormulaTestSerializer,
    FormulaValidateSerializer,
)
from apps.business_config.interfaces.views import _ConfigPermissions
from apps.pricing.domain.money import round_amount
from apps.product.infrastructure.models import Product


class FormulaCreateSerializer(serializers.Serializer):
    value = serializers.JSONField()
    effectiveFrom = serializers.DateField()
    effectiveTo = serializers.DateField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False, default=dict)
    productId = serializers.UUIDField(
        required=False, allow_null=True, default=None,
        help_text="Com produto, a versão é só desse produto (pricing.formulas@<produto>) e substitui a geral nele.",
    )


def _formulas_key(product_id) -> str:
    return product_key(CONFIG_KEY, product_id) if product_id else CONFIG_KEY


def _formulas(configuration_id) -> BusinessConfiguration:
    """Uma versão do conjunto de fórmulas: a geral ou a de um produto."""
    return get_object_or_404(
        BusinessConfiguration.objects.filter(
            Q(config_key=CONFIG_KEY) | Q(config_key__startswith=f"{CONFIG_KEY}{SEPARATOR}")
        ),
        id=configuration_id,
    )


def _with_analysis(configuration: BusinessConfiguration) -> dict:
    data = BusinessConfigurationSerializer(configuration).data
    try:
        data["analysis"] = {"valid": True, **parse_formula_set(configuration.value_json).describe()}
    except InvalidConfiguration as exc:  # dados antigos gravados antes da validação
        data["analysis"] = {"valid": False, "error": str(exc)}
    return data


def _simulation(value, total_amount, members_count, stage="QUOTE", age=None) -> dict:
    formula_set = parse_formula_set(value)
    outcome = evaluate_formula_set(
        formula_set, total_amount=total_amount, members_count=members_count, round_money=round_amount,
        stage=stage, age=age, explain=True,
    )
    return {
        "stage": stage,
        "baseTotal": str(outcome["baseTotal"]),
        "total": str(outcome["total"]),
        "steps": [
            {**step, **{k: str(step[k]) for k in ("before", "rawResult", "result", "adjustment")}}
            for step in outcome["steps"]
        ],
        "skipped": outcome["skipped"],
        **formula_set.describe(),
    }


class FormulaCatalogView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="getFormulaCatalog", summary="Variáveis, funções e operadores do editor de fórmulas",
                   tags=["Configuration"])
    def get(self, request):
        return Response(formula_catalog())


class FormulaVariablesView(_ConfigPermissions, APIView):
    """Catálogo único de variáveis: motor, parâmetros e auxiliares das
    fórmulas publicadas, campos do produto (`?productId=`) e campos das
    regras. Filtro `?usableIn=PRICING_FORMULAS|PRICING_FORMULAS:PERSON|
    PRICING_FORMULAS:QUOTE|PRODUCT_FORMULAS|RULE_CONDITIONS`."""

    @extend_schema(operation_id="getFormulaVariables", summary="Catálogo único das variáveis de fórmulas e regras",
                   tags=["Configuration"])
    def get(self, request):
        product_id = request.query_params.get("productId")
        if product_id:
            try:
                uuid.UUID(product_id)
            except ValueError:
                return Response({"valid": False, "error": "productId tem de ser um UUID"}, status=400)
            get_object_or_404(Product, id=product_id)
        return Response(variable_catalog(product_id=product_id, usable_in=request.query_params.get("usableIn")))


class FormulaListCreateView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="listFormulaSets", summary="Listar versões do conjunto de fórmulas", tags=["Configuration"],
                   parameters=[OpenApiParameter("productId", OpenApiTypes.UUID, description="Só as versões desse produto")])
    def get(self, request):
        product_id = request.query_params.get("productId") or None
        if product_id and not valid_product_id(product_id):
            raise ValidationError({"productId": "Identificador de produto inválido."})
        qs = BusinessConfiguration.objects.filter(config_key=_formulas_key(product_id)).order_by("-version_no")
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        return Response({"items": BusinessConfigurationSerializer(qs, many=True).data})

    @extend_schema(operation_id="createFormulaSet", summary="Criar nova versão (DRAFT) do conjunto de fórmulas",
                   tags=["Configuration"], request=FormulaCreateSerializer, responses={201: BusinessConfigurationSerializer})
    def post(self, request):
        s = FormulaCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        configuration = create_configuration(
            request, _formulas_key(data.get("productId")), data["value"], data["effectiveFrom"], data.get("effectiveTo"),
            data.get("metadata"),
        )
        return Response(_with_analysis(configuration), status=201)


class FormulaDetailView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="getFormulaSet", summary="Consultar versão do conjunto de fórmulas (com dependências)",
                   tags=["Configuration"])
    def get(self, request, configuration_id):
        return Response(_with_analysis(_formulas(configuration_id)))

    @extend_schema(operation_id="updateFormulaSet", summary="Editar conjunto de fórmulas em DRAFT ou REJECTED", tags=["Configuration"],
                   request=BusinessConfigurationUpdateSerializer)
    def put(self, request, configuration_id):
        s = BusinessConfigurationUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        configuration = update_configuration(
            request, _formulas(configuration_id), data["value"], data.get("effectiveFrom"), data.get("effectiveTo"),
            data.get("metadata"), data.get("rowVersion"),
        )
        return Response(_with_analysis(configuration))


class FormulaSubmitView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="submitFormulaSet", summary="Submeter conjunto de fórmulas para aprovação",
                   tags=["Configuration"], request=FormulaSubmitSerializer)
    def post(self, request, configuration_id):
        s = FormulaSubmitSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        configuration = submit_configuration(request, _formulas(configuration_id), s.validated_data.get("changeReason"))
        return Response(_with_analysis(configuration))


class FormulaApproveView(_ConfigPermissions, APIView):
    approve = True

    @extend_schema(operation_id="approveFormulaSet", summary="Aprovar e publicar conjunto de fórmulas",
                   tags=["Configuration"], request=None)
    def post(self, request, configuration_id):
        return Response(_with_analysis(approve_configuration(request, _formulas(configuration_id))))


class FormulaRejectView(_ConfigPermissions, APIView):
    approve = True

    @extend_schema(operation_id="rejectFormulaSet", summary="Rejeitar conjunto de fórmulas pendente",
                   tags=["Configuration"], request=BusinessConfigurationRejectSerializer)
    def post(self, request, configuration_id):
        s = BusinessConfigurationRejectSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(_with_analysis(reject_configuration(request, _formulas(configuration_id), s.validated_data["reason"])))


class FormulaRetireView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="retireFormulaSet", summary="Retirar (desativar) conjunto de fórmulas publicado",
                   tags=["Configuration"], request=None)
    def post(self, request, configuration_id):
        return Response(_with_analysis(retire_configuration(request, _formulas(configuration_id))))


class FormulaHistoryView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="getFormulaSetHistory", summary="Histórico de uma versão do conjunto de fórmulas",
                   tags=["Configuration"], responses=BusinessConfigurationHistorySerializer)
    def get(self, request, configuration_id):
        configuration = _formulas(configuration_id)
        return Response({"configurationId": str(configuration.id), "items": configuration_history(configuration)})


class FormulaSimulateView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="simulateFormulaSet",
                   summary="Simular uma versão (qualquer estado) com valores de entrada, sem gravar nada",
                   tags=["Configuration"], request=FormulaSimulateSerializer)
    def post(self, request, configuration_id):
        configuration = _formulas(configuration_id)
        s = FormulaSimulateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            data = s.validated_data
            result = _simulation(configuration.value_json, data["totalAmount"], data["membersCount"],
                                 data["stage"], data.get("age"))
        except FormulaError as exc:
            return Response({"valid": False, "error": str(exc)}, status=422)
        return Response({"valid": True, "configurationId": str(configuration.id),
                         "version": configuration.version_no, "status": configuration.status, **result})


class FormulaValidateView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="validateFormulaSet", summary="Validar um conjunto de fórmulas sem o gravar",
                   tags=["Configuration"], request=FormulaValidateSerializer)
    def post(self, request):
        s = FormulaValidateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            analysis = parse_formula_set(s.validated_data["value"]).describe()
        except InvalidConfiguration as exc:
            return Response({"valid": False, "error": str(exc)}, status=400)
        return Response({"valid": True, **analysis})


class FormulaTestView(_ConfigPermissions, APIView):
    """Testa uma expressão isolada sem guardar nem publicar alterações e
    devolve o cálculo passo a passo."""

    @extend_schema(operation_id="testPricingFormula", summary="Validar e testar uma expressão", tags=["Configuration"],
                   request=FormulaTestSerializer)
    def post(self, request):
        s = FormulaTestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        try:
            variables = sorted(referenced_names(data["expression"]))
            result, steps = explain_formula(data["expression"], data["variables"])
        except FormulaError as exc:
            return Response({"valid": False, "error": str(exc)}, status=400)
        # `steps`: o cálculo operação a operação, pela ordem em que é feito.
        return Response({"valid": True, "result": str(result), "variables": variables, "steps": steps})
