from django.urls import path

from apps.platform_admin.interfaces.views import (
    PlatformAdminListCreateView,
    PlatformAdminResetPasswordView,
    PlatformAdminStatusView,
    PlatformAuditView,
    PlatformChangePasswordView,
    PlatformLoginView,
    PlatformMeView,
    PlatformTenantAccountResetView,
    PlatformTenantAdminsView,
    PlatformTenantDetailView,
    PlatformTenantListCreateView,
)

urlpatterns = [
    path("platform/auth/login", PlatformLoginView.as_view(), name="platform-login"),
    path("platform/me", PlatformMeView.as_view(), name="platform-me"),
    path("platform/me/password", PlatformChangePasswordView.as_view(), name="platform-change-password"),
    path("platform/tenants", PlatformTenantListCreateView.as_view(), name="platform-tenants"),
    path("platform/tenants/<uuid:tenant_id>", PlatformTenantDetailView.as_view(), name="platform-tenant-detail"),
    path("platform/tenants/<uuid:tenant_id>/admins", PlatformTenantAdminsView.as_view(), name="platform-tenant-admins"),
    path("platform/tenants/<uuid:tenant_id>/accounts/<uuid:account_id>/reset-password",
         PlatformTenantAccountResetView.as_view(), name="platform-tenant-account-reset"),
    path("platform/admins", PlatformAdminListCreateView.as_view(), name="platform-admins"),
    path("platform/admins/<uuid:admin_id>", PlatformAdminStatusView.as_view(), name="platform-admin-status"),
    path("platform/admins/<uuid:admin_id>/reset-password", PlatformAdminResetPasswordView.as_view(), name="platform-admin-reset"),
    path("platform/audit", PlatformAuditView.as_view(), name="platform-audit"),
]
