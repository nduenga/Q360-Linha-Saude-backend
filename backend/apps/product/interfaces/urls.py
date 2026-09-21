from django.urls import path

from apps.product.interfaces.views import (
    BenefitListView,
    ConfigurationPublishView,
    ConfigurationRetireView,
    PlanBenefitDetailView,
    PlanBenefitListCreateView,
    PlanDetailView,
    PlanListCreateView,
    PricingParameterSetCreateView,
    PricingParameterSetDetailView,
    ProductDetailView,
    ProductListCreateView,
    ProductVersionCreateView,
    ProductVersionPublishView,
)

urlpatterns = [
    path("benefits", BenefitListView.as_view(), name="benefit-list"),
    path(
        "plans/<uuid:plan_id>/benefits",
        PlanBenefitListCreateView.as_view(),
        name="plan-benefit-list-create",
    ),
    path(
        "plans/<uuid:plan_id>/benefits/<uuid:benefit_id>",
        PlanBenefitDetailView.as_view(),
        name="plan-benefit-detail",
    ),
    path("products", ProductListCreateView.as_view(), name="product-list-create"),
    path("products/<uuid:product_id>", ProductDetailView.as_view(), name="product-detail"),
    path(
        "products/<uuid:product_id>/versions",
        ProductVersionCreateView.as_view(),
        name="product-version-create",
    ),
    path(
        "product-versions/<uuid:version_id>/publish",
        ProductVersionPublishView.as_view(),
        name="product-version-publish",
    ),
    path("plans", PlanListCreateView.as_view(), name="plan-list-create"),
    path("plans/<uuid:plan_id>", PlanDetailView.as_view(), name="plan-detail"),
    path(
        "pricing-parameter-sets",
        PricingParameterSetCreateView.as_view(),
        name="pricing-parameter-set-create",
    ),
    path(
        "pricing-parameter-sets/<uuid:parameter_set_id>",
        PricingParameterSetDetailView.as_view(),
        name="pricing-parameter-set-detail",
    ),
    path(
        "configuration/<str:config_type>/<uuid:config_id>/publish",
        ConfigurationPublishView.as_view(),
        name="configuration-publish",
    ),
    path(
        "configuration/<str:config_type>/<uuid:config_id>/retire",
        ConfigurationRetireView.as_view(),
        name="configuration-retire",
    ),
]
