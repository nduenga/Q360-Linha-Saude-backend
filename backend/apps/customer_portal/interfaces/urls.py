"""ROADMAP_PORTAL_CLIENTE.md Fase 0: a new, isolated URL namespace —
`/api/v1/customer-portal/...` — never reusing `/api/v1/quotes`,
`/api/v1/products`, etc."""
from __future__ import annotations

from django.urls import path

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
]
