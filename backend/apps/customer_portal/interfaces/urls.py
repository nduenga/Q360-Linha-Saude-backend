"""ROADMAP_PORTAL_CLIENTE.md Fase 0: a new, isolated URL namespace —
`/api/v1/customer-portal/...` — never reusing `/api/v1/quotes`,
`/api/v1/products`, etc."""
from __future__ import annotations

from django.urls import path

from apps.customer_portal.interfaces.self_service_views import (
    CustomerPortalCoverageView,
    CustomerPortalEligibilityView,
    CustomerPortalMeView,
    CustomerPortalPlanBenefitsView,
    CustomerPortalQuotesView,
)
from apps.customer_portal.interfaces.views import RequestAccessView, VerifyOtpView

urlpatterns = [
    path(
        "customer-portal/<uuid:tenant_id>/auth/request-access",
        RequestAccessView.as_view(),
        name="customer-portal-request-access",
    ),
    path(
        "customer-portal/<uuid:tenant_id>/auth/verify-otp",
        VerifyOtpView.as_view(),
        name="customer-portal-verify-otp",
    ),
    # Fase 1 (ROADMAP_PORTAL_CLIENTE.md) — authenticated via the portal's
    # own bearer token (CustomerPortalJwtAuthentication), which already
    # carries tenant_id, so no {tenant_id} path segment here (unlike the
    # 2 pre-auth routes above, which have no token yet to carry it).
    path("customer-portal/me", CustomerPortalMeView.as_view(), name="customer-portal-me"),
    path("customer-portal/me/quotes", CustomerPortalQuotesView.as_view(), name="customer-portal-me-quotes"),
    path("customer-portal/coverage", CustomerPortalCoverageView.as_view(), name="customer-portal-coverage"),
    path(
        "customer-portal/plan-benefits",
        CustomerPortalPlanBenefitsView.as_view(),
        name="customer-portal-plan-benefits",
    ),
    path(
        "customer-portal/eligibility",
        CustomerPortalEligibilityView.as_view(),
        name="customer-portal-eligibility",
    ),
]
