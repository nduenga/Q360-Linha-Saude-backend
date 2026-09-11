"""Controllers for the product module. Every `security` scope and
permission combination below is copied from ART-006's `security` block for
that exact `operationId` — see the operationId noted in each view's
docstring to cross-check against docs/artifacts/ART-006-openapi/.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.permissions import require_permission, require_scope
from apps.product.application import product_service
from apps.product.application.configuration import publish_configuration
from apps.product.application.pricing_parameter_service import create_pricing_parameter_set
from apps.product.application.use_cases import PublishProductVersionUseCase
from apps.product.infrastructure.models import Plan, Product, ProductVersion
from apps.product.interfaces.serializers import (
    PlanCreateRequestSerializer,
    PlanSerializer,
    PricingParameterSetRequestSerializer,
    ProductCreateRequestSerializer,
    ProductSerializer,
    ProductUpdateRequestSerializer,
    ProductVersionCreateRequestSerializer,
    ProductVersionSerializer,
    VersionedConfigHeaderSerializer,
)
from shared.pagination import Q360PageNumberPagination


class ProductListCreateView(APIView):
    """ART-006 `/api/v1/products`: `listProducts` (GET), `createProduct` (POST)."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.WRITE)(), require_permission(Permission.PRODUCT_MANAGE)()]
        return [require_scope(Scope.READ)()]

    def get(self, request):
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(Product.objects.all().order_by("code"), request)
        return paginator.get_paginated_response(ProductSerializer(page, many=True).data)

    def post(self, request):
        body = ProductCreateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        product = product_service.create_product(**body.validated_data)
        return Response(ProductSerializer(product).data, status=201)


class ProductDetailView(APIView):
    """ART-006 `/api/v1/products/{productId}`: `getProduct` (GET), `updateProduct` (PUT)."""

    def get_permissions(self):
        if self.request.method == "PUT":
            return [require_scope(Scope.WRITE)(), require_permission(Permission.PRODUCT_MANAGE)()]
        return [require_scope(Scope.READ)()]

    def get(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        return Response(ProductSerializer(product).data)

    def put(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        body = ProductUpdateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        updated = product_service.update_product(product=product, **body.validated_data)
        return Response(ProductSerializer(updated).data)


class ProductVersionCreateView(APIView):
    """ART-006 `/api/v1/products/{productId}/versions`: `createProductVersion` (POST)."""

    permission_classes = [require_scope(Scope.ADMIN), require_permission(Permission.PRODUCT_MANAGE)]

    def post(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        body = ProductVersionCreateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        version = product_service.create_product_version(
            product=product,
            effective_from=body.validated_data["effectiveFrom"],
            effective_to=body.validated_data["effectiveTo"],
        )
        return Response(ProductVersionSerializer(version).data, status=201)


class ProductVersionPublishView(APIView):
    """ART-006 `/api/v1/product-versions/{versionId}/publish`: `publishProductVersion` (POST)."""

    permission_classes = [require_scope(Scope.ADMIN), require_permission(Permission.PRODUCT_MANAGE)]

    def post(self, request, version_id):
        version = get_object_or_404(ProductVersion, id=version_id)
        published = PublishProductVersionUseCase().execute(version)
        return Response(ProductVersionSerializer(published).data)


class PlanListCreateView(APIView):
    """ART-006 `/api/v1/plans`: `listPlans` (GET), `createPlan` (POST)."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.ADMIN)(), require_permission(Permission.PRODUCT_MANAGE)()]
        return [require_scope(Scope.READ)()]

    def get(self, request):
        queryset = Plan.objects.all().order_by("code")
        product_version_id = request.query_params.get("productVersionId")
        if product_version_id:
            queryset = queryset.filter(product_version_id=product_version_id)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(PlanSerializer(page, many=True).data)

    def post(self, request):
        body = PlanCreateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        product_version = get_object_or_404(ProductVersion, id=body.validated_data["productVersionId"])
        plan = product_service.create_plan(
            product_version=product_version,
            code=body.validated_data["code"],
            name=body.validated_data["name"],
            description=body.validated_data["description"],
        )
        return Response(PlanSerializer(plan).data, status=201)


class PlanDetailView(APIView):
    """ART-006 `/api/v1/plans/{planId}`: `getPlan` (GET)."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, plan_id):
        plan = get_object_or_404(Plan, id=plan_id)
        return Response(PlanSerializer(plan).data)


class PricingParameterSetCreateView(APIView):
    """ART-006 `/api/v1/pricing-parameter-sets`: `createPricingParameterSet` (POST)."""

    permission_classes = [require_scope(Scope.ADMIN), require_permission(Permission.PRICING_CONFIG_MANAGE)]

    def post(self, request):
        body = PricingParameterSetRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        parameter_rows = [p["_row"] for p in body.validated_data["parameters"]]
        parameter_set = create_pricing_parameter_set(
            code=body.validated_data["code"],
            effective_from=body.validated_data["effectiveFrom"],
            effective_to=body.validated_data["effectiveTo"],
            parameter_rows=parameter_rows,
        )
        return Response(VersionedConfigHeaderSerializer(parameter_set).data, status=201)


class ConfigurationPublishView(APIView):
    """ART-006 `/api/v1/configuration/{configType}/{configId}/publish`:
    `publishConfiguration` (POST).

    Gated by ART-006 scope only (q360.admin): this one endpoint spans
    `pricing-parameter-set` (DOC-001 `pricing-config:manage`) and
    `rule-version` (rule_domain can be ELIGIBILITY, not pricing at all —
    no DOC-001 permission fits every config_type uniformly), so no
    `require_permission` is applied here.
    """

    permission_classes = [require_scope(Scope.ADMIN)]

    def post(self, request, config_type, config_id):
        published = publish_configuration(config_type=config_type, config_id=config_id)
        return Response(published)
