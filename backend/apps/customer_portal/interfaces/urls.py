"""ROADMAP_PORTAL_CLIENTE.md Fase 0: a new, isolated URL namespace —
`/api/v1/customer-portal/...` — never reusing `/api/v1/quotes`,
`/api/v1/products`, etc."""
from __future__ import annotations

from django.urls import path

from apps.customer_portal.interfaces.comm_views import (
    CustomerPortalConversationsView,
    CustomerPortalMessagesView,
    CustomerPortalNotificationsReadView,
    CustomerPortalNotificationsView,
    CustomerPortalPlanCompareView,
    CustomerPortalRenewalView,
    CustomerPortalRequestDetailView,
    CustomerPortalRequestsView,
    CustomerPortalRequestTypesView,
)
from apps.customer_portal.interfaces.portal_views import (
    CustomerPortalBeneficiariesView,
    CustomerPortalCardView,
    CustomerPortalDashboardView,
    CustomerPortalDocumentDownloadView,
    CustomerPortalDocumentsView,
    CustomerPortalPaymentsView,
    CustomerPortalPolicyDetailView,
    CustomerPortalPolicyDocumentView,
    CustomerPortalPolicyStatementView,
    CustomerPortalPolicyHistoryView,
    CustomerPortalPolicyListView,
    CustomerPortalProfileView,
    CustomerPortalQuoteDetailView,
)
from apps.customer_portal.interfaces.staff_views import (
    PortalConversationListView,
    PortalRequestDetailView,
    PortalRequestListView,
    PortalRequestTransitionView,
    PortalStaffMessagesView,
)
from apps.customer_portal.interfaces.self_service_views import (
    CustomerPortalCoverageView,
    CustomerPortalEligibilityView,
    CustomerPortalMeView,
    CustomerPortalPlanBenefitsView,
    CustomerPortalQuotesView,
)
from apps.customer_portal.interfaces.views import (
    FirstAccessConfirmView,
    FirstAccessRequestView,
    PasswordLoginView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RequestAccessView,
    VerifyOtpView,
)

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
    # Login por email + palavra-passe (password_auth_service.py).
    path("customer-portal/<uuid:tenant_id>/auth/login", PasswordLoginView.as_view(), name="customer-portal-login"),
    path("customer-portal/<uuid:tenant_id>/auth/first-access/request", FirstAccessRequestView.as_view(), name="customer-portal-first-access-request"),
    path("customer-portal/<uuid:tenant_id>/auth/first-access/confirm", FirstAccessConfirmView.as_view(), name="customer-portal-first-access-confirm"),
    path("customer-portal/<uuid:tenant_id>/auth/password-reset/request", PasswordResetRequestView.as_view(), name="customer-portal-password-reset-request"),
    path("customer-portal/<uuid:tenant_id>/auth/password-reset/confirm", PasswordResetConfirmView.as_view(), name="customer-portal-password-reset-confirm"),
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
    # PDF Portal Cliente — MVP read endpoints (portal_views.py).
    path("customer-portal/dashboard", CustomerPortalDashboardView.as_view(), name="customer-portal-dashboard"),
    path("customer-portal/me/quotes/<str:quote_number>", CustomerPortalQuoteDetailView.as_view(), name="customer-portal-quote-detail"),
    path("customer-portal/policies", CustomerPortalPolicyListView.as_view(), name="customer-portal-policies"),
    path("customer-portal/policies/<str:policy_number>", CustomerPortalPolicyDetailView.as_view(), name="customer-portal-policy-detail"),
    path("customer-portal/policies/<str:policy_number>/document", CustomerPortalPolicyDocumentView.as_view(), name="customer-portal-policy-document"),
    path("customer-portal/policies/<str:policy_number>/statement", CustomerPortalPolicyStatementView.as_view(), name="customer-portal-policy-statement"),
    path("customer-portal/policies/<str:policy_number>/history", CustomerPortalPolicyHistoryView.as_view(), name="customer-portal-policy-history"),
    path("customer-portal/policies/<str:policy_number>/members/<uuid:member_id>/card", CustomerPortalCardView.as_view(), name="customer-portal-card"),
    path("customer-portal/beneficiaries", CustomerPortalBeneficiariesView.as_view(), name="customer-portal-beneficiaries"),
    path("customer-portal/payments", CustomerPortalPaymentsView.as_view(), name="customer-portal-payments"),
    path("customer-portal/documents", CustomerPortalDocumentsView.as_view(), name="customer-portal-documents"),
    path("customer-portal/documents/<uuid:document_id>/download", CustomerPortalDocumentDownloadView.as_view(), name="customer-portal-document-download"),
    path("customer-portal/profile", CustomerPortalProfileView.as_view(), name="customer-portal-profile"),
    # PDF Portal Cliente — pedidos, mensagens, notificações, renovação, comparação (comm_views.py).
    path("customer-portal/request-types", CustomerPortalRequestTypesView.as_view(), name="customer-portal-request-types"),
    path("customer-portal/requests", CustomerPortalRequestsView.as_view(), name="customer-portal-requests"),
    path("customer-portal/requests/<str:request_number>", CustomerPortalRequestDetailView.as_view(), name="customer-portal-request-detail"),
    path("customer-portal/messages", CustomerPortalMessagesView.as_view(), name="customer-portal-messages"),
    path("customer-portal/conversations", CustomerPortalConversationsView.as_view(), name="customer-portal-conversations"),
    path("customer-portal/notifications", CustomerPortalNotificationsView.as_view(), name="customer-portal-notifications"),
    path("customer-portal/notifications/read", CustomerPortalNotificationsReadView.as_view(), name="customer-portal-notifications-read"),
    path("customer-portal/policies/<str:policy_number>/renewal", CustomerPortalRenewalView.as_view(), name="customer-portal-renewal"),
    path("customer-portal/plans/compare", CustomerPortalPlanCompareView.as_view(), name="customer-portal-plan-compare"),
    # Backoffice — atendimento dos pedidos e mensagens do portal (staff_views.py).
    path("portal-requests", PortalRequestListView.as_view(), name="portal-requests"),
    path("portal-requests/<str:request_number>", PortalRequestDetailView.as_view(), name="portal-request-detail"),
    path("portal-requests/<str:request_number>/transition", PortalRequestTransitionView.as_view(), name="portal-request-transition"),
    path("portal-conversations", PortalConversationListView.as_view(), name="portal-conversations"),
    path("portal-messages", PortalStaffMessagesView.as_view(), name="portal-messages"),
]
