from django.urls import path

from apps.claims.interfaces.views import (
    AssumptionSetDetailView,
    AssumptionSetListCreateView,
    ClaimsImportDetailView,
    ClaimsImportListCreateView,
    ClaimsProfitSharingView,
    ClaimsProfitSharingParametersView,
    ClaimsMethodologyView,
    ClaimsImportTemplateView,
    ClaimsSummaryView,
    ProjectionDetailView,
    ProjectionListCreateView,
)

urlpatterns = [
    path("claims/imports", ClaimsImportListCreateView.as_view(), name="claims-imports"),
    path("claims/imports/<uuid:import_id>", ClaimsImportDetailView.as_view(), name="claims-import-detail"),
    path("claims/methodology", ClaimsMethodologyView.as_view(), name="claims-methodology"),
    path("claims/import-template", ClaimsImportTemplateView.as_view(), name="claims-import-template"),
    path("claims/summary", ClaimsSummaryView.as_view(), name="claims-summary"),
    path("claims/profit-sharing", ClaimsProfitSharingView.as_view(), name="claims-profit-sharing"),
    path(
        "claims/profit-sharing/parameters",
        ClaimsProfitSharingParametersView.as_view(),
        name="claims-profit-sharing-parameters",
    ),
    path("claims/assumption-sets", AssumptionSetListCreateView.as_view(), name="claims-assumption-sets"),
    path("claims/assumption-sets/<uuid:set_id>", AssumptionSetDetailView.as_view(), name="claims-assumption-set-detail"),
    path("claims/projections", ProjectionListCreateView.as_view(), name="claims-projections"),
    path("claims/projections/<uuid:run_id>", ProjectionDetailView.as_view(), name="claims-projection-detail"),
]
