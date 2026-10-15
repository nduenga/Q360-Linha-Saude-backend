"""API da configuração de tarifação por produto: grupos de opções, campos,
valores («Taxas e Valores») e fórmulas, como os separadores do produto.

O rascunho grava-se em `PUT /products/{id}/pricing-setup`; submeter,
aprovar (outra pessoa), rejeitar, comparar versões e anexar documentos usam
as rotas gerais `/business-config/configurations/{configurationId}/…`.
"""
from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.business_config.application import product_setup_service
from apps.business_config.domain.product_setup import catalog, evaluate_product_setup, parse_product_setup
from apps.business_config.interfaces.serializers import BusinessConfigurationSerializer
from apps.business_config.interfaces.views import _ConfigPermissions
from apps.business_config.domain.errors import InvalidConfiguration
from apps.product.infrastructure.models import Product


class ProductSetupSaveSerializer(serializers.Serializer):
    value = serializers.JSONField(help_text="{optionGroups, fields, values, formulas} — ver a descrição da rota.")
    effectiveFrom = serializers.DateField(required=False, allow_null=True, default=None)
    rowVersion = serializers.IntegerField(required=False, allow_null=True, default=None, min_value=0)


class ProductSetupValidateSerializer(serializers.Serializer):
    value = serializers.JSONField()


class ProductSetupTestSerializer(serializers.Serializer):
    value = serializers.JSONField(required=False, allow_null=True, default=None,
                                  help_text="Configuração a testar; por omissão o rascunho, senão a publicada.")
    expression = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None,
                                       help_text="Expressão avulsa a testar (como no editor), sem a guardar.")
    productOptions = serializers.JSONField(required=False, default=dict, help_text="{grupo: [opções]}")
    productFields = serializers.JSONField(required=False, default=dict, help_text="{campo: valor}")
    ages = serializers.ListField(child=serializers.IntegerField(min_value=0, max_value=150), required=False, default=list)
    technicalPremium = serializers.DecimalField(max_digits=20, decimal_places=2, required=False, allow_null=True, default=None)
    members = serializers.IntegerField(required=False, allow_null=True, default=None, min_value=0)
    category = serializers.CharField(required=False, allow_null=True, default=None)
    planCode = serializers.CharField(required=False, allow_null=True, default=None)
    policyType = serializers.ChoiceField(choices=["INDIVIDUAL", "GROUP"], required=False, allow_null=True, default=None)
    requireAll = serializers.BooleanField(required=False, default=False,
                                          help_text="Exigir os grupos/campos obrigatórios (como numa cotação).")


_STATE = inline_serializer("ProductPricingSetupState", fields={
    "productId": serializers.UUIDField(),
    "productCode": serializers.CharField(),
    "configKey": serializers.CharField(),
    "published": serializers.DictField(allow_null=True, help_text="Versão em vigor (id, versionNo, value, …)."),
    "draft": serializers.DictField(allow_null=True, help_text="Rascunho aberto (DRAFT ou REJECTED)."),
    "pendingApproval": serializers.DictField(allow_null=True),
    "tokens": serializers.ListField(child=serializers.DictField(), help_text="Grupos, opções, campos, fórmulas e variáveis do sistema que o editor pode usar."),
    "form": serializers.DictField(allow_null=True, help_text="Formulário da cotação (versão publicada)."),
})
_RESULT = inline_serializer("ProductPricingSetupTestResult", fields={
    "results": serializers.ListField(child=serializers.DictField(), help_text="Uma linha por fórmula: code, name, value, unit, flags, frequency, applies."),
    "groupValues": serializers.DictField(),
    "premium": serializers.CharField(allow_null=True),
    "premiumFormula": serializers.CharField(allow_null=True),
    "installments": serializers.DictField(help_text="Prestação por frequência (fórmulas de fracionamento)."),
    "selection": serializers.DictField(),
    "expressionValue": serializers.CharField(required=False),
})


def _product(product_id) -> Product:
    return get_object_or_404(Product, id=product_id)


class ProductPricingSetupView(_ConfigPermissions, APIView):
    """Configuração de tarifação do produto (separadores Grupo de opções,
    Campos, Formulário, Valores e Fórmulas). GET devolve a versão em vigor, o
    rascunho, a versão à espera de aprovação, os blocos do editor de fórmulas
    e o formulário da cotação. PUT grava o rascunho (cria uma versão DRAFT ou
    edita a aberta); depois submete-se e aprova-se em
    `/business-config/configurations/{id}` e `/approve`.

    Valor: `optionGroups[]` {code, name, listType RADIO|SELECT|CHECKBOX|TOGGLE|AUTOCOMPLETE,
    required, maxSelected, showInForm, order, options[{code,label}]}; `fields[]` {code, label,
    type NUMBER|INTEGER|TEXT|DATE|BOOLEAN, required, min, max, default, unit, order};
    `values[]` {group, type SIMPLE|MULTIPLE|FIXED|AGE_INTERVAL|FIELD_VALUE|OPTION_CONDITIONAL,
    aggregate SUM|PRODUCT|MAX|MIN, unit, value, field, conditionGroup, rows[]}; `formulas[]`
    {code, name, expression, flags{premium,capital,hidden,fractionation,conversion},
    frequency, unit, minResult, order, active, scope{categories,plans,policyTypes}}."""

    @extend_schema(operation_id="getProductPricingSetup", tags=["Configuration"], responses={200: _STATE})
    def get(self, request, product_id):
        return Response(product_setup_service.state(_product(product_id)))

    @extend_schema(operation_id="saveProductPricingSetupDraft", tags=["Configuration"],
                   request=ProductSetupSaveSerializer, responses={200: BusinessConfigurationSerializer})
    def put(self, request, product_id):
        product = _product(product_id)
        body = ProductSetupSaveSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        if not isinstance(data["value"], dict):
            raise InvalidConfiguration("value tem de ser um objeto {optionGroups, fields, values, formulas}")
        saved = product_setup_service.save_draft(
            request, product, value=data["value"], effective_from=data["effectiveFrom"], row_version=data["rowVersion"]
        )
        return Response(BusinessConfigurationSerializer(saved).data)


class ProductPricingSetupValidateView(_ConfigPermissions, APIView):
    """Valida uma configuração sem a guardar (sintaxe das fórmulas, nomes
    usados, dependências circulares, opções e valores). Devolve os blocos
    do editor e a ordem de cálculo."""

    @extend_schema(operation_id="validateProductPricingSetup", tags=["Configuration"],
                   request=ProductSetupValidateSerializer,
                   responses={200: inline_serializer("ProductPricingSetupValidation", fields={
                       "valid": serializers.BooleanField(), "evaluationOrder": serializers.ListField(child=serializers.CharField()),
                       "tokens": serializers.ListField(child=serializers.DictField())})})
    def post(self, request, product_id):
        _product(product_id)
        body = ProductSetupValidateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        setup = parse_product_setup(body.validated_data["value"])
        return Response({"valid": True, "evaluationOrder": list(setup.evaluation_order), "tokens": setup.tokens()})


class ProductPricingSetupTestView(_ConfigPermissions, APIView):
    """«Testar fórmula»: calcula as fórmulas com valores de exemplo (opções,
    campos, idades, prémio técnico) sem guardar nada. Com `expression`,
    calcula também essa expressão avulsa."""

    @extend_schema(operation_id="testProductPricingSetup", tags=["Configuration"],
                   request=ProductSetupTestSerializer, responses={200: _RESULT})
    def post(self, request, product_id):
        product = _product(product_id)
        body = ProductSetupTestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        setup = product_setup_service.working_setup(product, data["value"])
        result = evaluate_product_setup(
            setup, options=data["productOptions"], fields=data["productFields"], ages=data["ages"],
            technical_premium=data["technicalPremium"], members_count=data["members"], category=data["category"],
            plan_code=data["planCode"], policy_type=data["policyType"], require=data["requireAll"],
            extra_expression=data["expression"] or None,
        )
        return Response(result)


class ProductPricingSetupHistoryView(_ConfigPermissions, APIView):
    """Histórico das versões da configuração do produto (mais recente primeiro)."""

    @extend_schema(operation_id="listProductPricingSetupHistory", tags=["Configuration"],
                   responses={200: inline_serializer("ProductPricingSetupHistory", fields={
                       "items": serializers.ListField(child=serializers.DictField())})})
    def get(self, request, product_id):
        return Response({"items": product_setup_service.history(_product(product_id))})


class ProductPricingSetupFormView(_ConfigPermissions, APIView):
    """Formulário da cotação para o produto (versão publicada): grupos de
    opções e campos visíveis, por ordem. As escolhas vão em
    `PUT /quotes/{id}/selection` como `productOptions` e `productFields`."""

    @extend_schema(operation_id="getProductPricingSetupForm", tags=["Configuration"],
                   responses={200: inline_serializer("ProductPricingSetupForm", fields={
                       "items": serializers.ListField(child=serializers.DictField())})})
    def get(self, request, product_id):
        product = _product(product_id)
        row = product_setup_service.published(product.id)
        return Response(parse_product_setup(row.value_json).form() if row else {"items": []})


class ProductPricingSetupCatalogView(_ConfigPermissions, APIView):
    """Opções do editor: tipos de lista, de campo e de valor, agregações,
    unidades, frequências, indicadores das fórmulas e variáveis do sistema."""

    @extend_schema(operation_id="getProductPricingSetupCatalog", tags=["Configuration"], responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(catalog())
