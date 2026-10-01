from django.urls import path

from apps.pricing.interfaces.views import (
    PricingCalculateView,
    PricingExplanationView,
    PricingPreviewView,
    PricingScenarioView,
    PricingExecutionListView,
    PricingExecutionDetailView,
    RatingTableCreateView,
    RatingTableDetailView,
)

urlpatterns = [
    path("rating-tables", RatingTableCreateView.as_view(), name="rating-table-create"),
    path("rating-tables/<uuid:rating_table_id>", RatingTableDetailView.as_view(), name="rating-table-detail"),
    path("pricing/calculate", PricingCalculateView.as_view(), name="pricing-calculate"),
    path("pricing/preview", PricingPreviewView.as_view(), name="pricing-preview"),
    path(
        "pricing/<uuid:pricing_run_id>/explanation",
        PricingExplanationView.as_view(),
        name="pricing-explanation",
    ),
    path("pricing/scenarios", PricingScenarioView.as_view(), name="pricing-scenario-create"),
    path(
        "pricing/runs",
        PricingExecutionListView.as_view(),
        name="pricing-execution-list",
    ),
    path(
        "pricing/runs/<uuid:pricing_run_id>",
        PricingExecutionDetailView.as_view(),
        name="pricing-execution-detail",
    ),

]
