from django.urls import path

from apps.pricing.interfaces.views import (
    PricingCalculateView,
    PricingExplanationView,
    PricingScenarioView,
    RatingTableCreateView,
)

urlpatterns = [
    path("rating-tables", RatingTableCreateView.as_view(), name="rating-table-create"),
    path("pricing/calculate", PricingCalculateView.as_view(), name="pricing-calculate"),
    path(
        "pricing/<uuid:pricing_run_id>/explanation",
        PricingExplanationView.as_view(),
        name="pricing-explanation",
    ),
    path("pricing/scenarios", PricingScenarioView.as_view(), name="pricing-scenario-create"),
]
