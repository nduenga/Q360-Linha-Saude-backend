"""Controllers for the product module. Every `security` scope and
permission combination below is copied from ART-006's `security` block for
that exact `operationId` — see the operationId noted in each view's
docstring to cross-check against docs/artifacts/ART-006-openapi/."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import requires_idempotency
from apps.foundation.interfaces.permissions import require_permission, require_scope
from apps.product.application import product_service
from apps.product.application.benefit_service import (
    add_plan_benefit,
    list_benefits,
    list_plan_benefits,
    remove_plan_benefit,
)
from apps.product.application.configuration import publish_configuration, retire_configuration
from apps.product.application.pricing_parameter_service import (
    create_pricing_parameter_set,
    delete_pricing_parameter_set,
    update_pricing_parameter_set,
)
from apps.product.infrastructure.models import Benefit, Plan, PricingParameterSet, Product
from apps.product.interfaces.serializers import (
    AddPlanBenefitRequestSerializer,
    BenefitSerializer,
    PlanBenefitSerializer,
    PlanCreateRequestSerializer,
    PlanSerializer,
    PlanUpdateRequestSerializer,
    PricingParameterSetRequestSerializer,
    PricingParameterSetUpdateRequestSerializer,
    ProductCreateRequestSerializer,
    ProductSerializer,
    ProductUpdateRequestSerializer,
    VersionedConfigHeaderSerializer,
)
from shared.pagination import Q360PageNumberPagination


@requires_idempotency
class ProductListCreateView(APIView):
    """ART-006 `/api/v1/products`: `listProducts` (GET), `createProduct` (POST)."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.WRITE)(), require_permission(Permission.PRODUCT_MANAGE)()]
        return [require_scope(Scope.READ)()]

    def get(self, request):
        # `?status=` is a pragmatic V1 addition, not in ART-006 (same
        # posture as the equivalent filter on PricingParameterSet/
        # RatingTable/RuleVersion list endpoints) - lets the frontend ask
        # for ACTIVE only where a product picker must never offer a
        # DRAFT/INACTIVE/ARCHIVED one (e.g. starting a new quote).
        queryset = Product.objects.all().order_by("code")
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ProductSerializer(page, many=True).data)

    def post(self, request):
        body = ProductCreateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        product = product_service.create_product(**body.validated_data)
        return Response(ProductSerializer(product).data, status=201)


@requires_idempotency
class ProductDetailView(APIView):
    """ART-006 `/api/v1/products/{productId}`: `getProduct` (GET),
    `updateProduct` (PUT). `DELETE` is a pragmatic V1 addition, not in
    ART-006 - only works while the product has no ProductVersion yet (409
    CONFLICT otherwise; see product_service.delete_product)."""

    def get_permissions(self):
        if self.request.method in ("PUT", "DELETE"):
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

    def delete(self, request, product_id):
        product = get_object_or_404(Product, id=product_id)
        product_service.delete_product(product=product)
        return Response(status=204)


class PlanListCreateView(APIView):
    """ART-006 `/api/v1/plans`: `listPlans` (GET), `createPlan` (POST).

    DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6, 2026-09-26): no more
    `/products/{id}/versions` or `/product-versions/{id}/publish` — a Plan
    is created directly under a Product, filterable by `productId`."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.ADMIN)(), require_permission(Permission.PRODUCT_MANAGE)()]
        return [require_scope(Scope.READ)()]

    def get(self, request):
        queryset = Plan.objects.all().order_by("code")
        product_id = request.query_params.get("productId")
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(PlanSerializer(page, many=True).data)

    def post(self, request):
        body = PlanCreateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        product = get_object_or_404(Product, id=body.validated_data["productId"])
        plan = product_service.create_plan(
            product=product,
            code=body.validated_data["code"],
            name=body.validated_data["name"],
            description=body.validated_data["description"],
            complementary_benefit_ids=body.validated_data["complementaryBenefitIds"],
        )
        return Response(PlanSerializer(plan).data, status=201)


@requires_idempotency
class PlanDetailView(APIView):
    """ART-006 `/api/v1/plans/{planId}`: `getPlan` (GET). `PATCH`/`DELETE`
    are a pragmatic V1 addition, not in ART-006. DECISIONS_TAKEN.md#S09-
    POLICY-001 (PO-APO-6): a Plan can be edited/deleted at any time now (no
    more parent-version DRAFT gate) — delete is still blocked with 409 if a
    Quote/PricingRun/eligibility evaluation already references this Plan
    (product_service.delete_plan)."""

    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [require_scope(Scope.ADMIN)(), require_permission(Permission.PRODUCT_MANAGE)()]
        return [require_scope(Scope.READ)()]

    def get(self, request, plan_id):
        plan = get_object_or_404(Plan, id=plan_id)
        return Response(PlanSerializer(plan).data)

    def patch(self, request, plan_id):
        plan = get_object_or_404(Plan, id=plan_id)
        body = PlanUpdateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        updated = product_service.update_plan(plan=plan, **body.validated_data)
        return Response(PlanSerializer(updated).data)

    def delete(self, request, plan_id):
        plan = get_object_or_404(Plan, id=plan_id)
        product_service.delete_plan(plan=plan)
        return Response(status=204)


@requires_idempotency
class PricingParameterSetCreateView(APIView):
    """ART-006 `/api/v1/pricing-parameter-sets`: `createPricingParameterSet`
    (POST). `GET` (list) is a pragmatic V1 addition, not in ART-006 — see
    OPEN_DECISIONS.md#S04-LISTING-GAPS-001/DECISIONS_TAKEN.md."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.ADMIN)(), require_permission(Permission.PRICING_CONFIG_MANAGE)()]
        return [require_scope(Scope.READ)()]

    def get(self, request):
        queryset = PricingParameterSet.objects.all().order_by("code", "-version_no")
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(VersionedConfigHeaderSerializer(page, many=True).data)

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


@requires_idempotency
class PricingParameterSetDetailView(APIView):
    """ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 6, pragmatic V1 addition, not
    in ART-006. `PATCH`/`DELETE` only work while `status=DRAFT`."""

    permission_classes = [require_scope(Scope.ADMIN), require_permission(Permission.PRICING_CONFIG_MANAGE)]

    def patch(self, request, parameter_set_id):
        parameter_set = get_object_or_404(PricingParameterSet, id=parameter_set_id)
        body = PricingParameterSetUpdateRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        parameter_rows = [p["_row"] for p in body.validated_data["parameters"]]
        updated = update_pricing_parameter_set(parameter_set, parameter_rows=parameter_rows)
        return Response(VersionedConfigHeaderSerializer(updated).data)

    def delete(self, request, parameter_set_id):
        parameter_set = get_object_or_404(PricingParameterSet, id=parameter_set_id)
        delete_pricing_parameter_set(parameter_set)
        return Response(status=204)


@requires_idempotency
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


@requires_idempotency
class ConfigurationRetireView(APIView):
    """`/api/v1/configuration/{configType}/{configId}/retire` —
    ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 6 (OD-ANGOLA-006), pragmatic V1
    addition alongside the existing publish dispatcher, same `configType`
    closed set (pricing-parameter-set/rule-version/rating-table), not in
    ART-006."""

    permission_classes = [require_scope(Scope.ADMIN)]

    def post(self, request, config_type, config_id):
        retired = retire_configuration(config_type=config_type, config_id=config_id)
        return Response(retired)


class BenefitListView(APIView):
    """Pragmatic V1 addition, not in ART-006 — see
    apps/product/application/benefit_service.py module docstring and
    ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 1. Lists the fixed 11-coverage
    market catalogue (3 BASE + 8 COMPLEMENTARY), seeding it for the
    tenant on first use."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        queryset = list_benefits(category=request.query_params.get("category"))
        paginator = Q360PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(BenefitSerializer(page, many=True).data)


@requires_idempotency
class PlanBenefitListCreateView(APIView):
    """Pragmatic V1 addition, not in ART-006. `GET` lists the coverages
    currently attached to a Plan (BASE + whichever COMPLEMENTARY ones were
    opted into); `POST` attaches one more COMPLEMENTARY coverage (BASE
    ones are attached automatically by product_service.create_plan and
    never opted into here)."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [require_scope(Scope.ADMIN)(), require_permission(Permission.PRODUCT_MANAGE)()]
        return [require_scope(Scope.READ)()]

    def get(self, request, plan_id):
        plan = get_object_or_404(Plan, id=plan_id)
        queryset = list_plan_benefits(plan=plan)
        return Response(PlanBenefitSerializer(queryset, many=True).data)

    def post(self, request, plan_id):
        plan = get_object_or_404(Plan, id=plan_id)
        body = AddPlanBenefitRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        benefit = get_object_or_404(Benefit, id=body.validated_data["benefitId"])
        plan_benefit = add_plan_benefit(plan=plan, benefit=benefit)
        return Response(PlanBenefitSerializer(plan_benefit).data, status=201)


class PlanBenefitDetailView(APIView):
    """Pragmatic V1 addition, not in ART-006. `DELETE` detaches a
    COMPLEMENTARY coverage from a Plan — a BASE coverage can never be
    removed this way (benefit_service.remove_plan_benefit raises
    MissingCoreBenefitsError, mapped to 400 VALIDATION-400)."""

    permission_classes = [require_scope(Scope.ADMIN), require_permission(Permission.PRODUCT_MANAGE)]

    def delete(self, request, plan_id, benefit_id):
        plan = get_object_or_404(Plan, id=plan_id)
        benefit = get_object_or_404(Benefit, id=benefit_id)
        remove_plan_benefit(plan=plan, benefit=benefit)
        return Response(status=204)
