from __future__ import annotations

from django.urls import path

from apps.staff_accounts.interfaces.admin_views import (
    StaffAccountListCreateView,
    StaffAccountResetPasswordView,
    StaffAccountUnlockView,
    StaffAccountRolesView,
    StaffAccountStatusView,
)
from apps.staff_accounts.interfaces.views import LoginView, LogoutView, RefreshView

urlpatterns = [
    path("auth/login", LoginView.as_view(), name="staff-login"),
    path("auth/refresh", RefreshView.as_view(), name="staff-refresh"),
    path("auth/logout", LogoutView.as_view(), name="staff-logout"),
    path("admin/staff-accounts", StaffAccountListCreateView.as_view(), name="staff-accounts-list-create"),
    path(
        "admin/staff-accounts/<uuid:account_id>/roles",
        StaffAccountRolesView.as_view(),
        name="staff-accounts-roles",
    ),
    path(
        "admin/staff-accounts/<uuid:account_id>/status",
        StaffAccountStatusView.as_view(),
        name="staff-accounts-status",
    ),
    path(
        "admin/staff-accounts/<uuid:account_id>/reset-password",
        StaffAccountResetPasswordView.as_view(),
        name="staff-accounts-reset-password",
    ),
    path(
        "admin/staff-accounts/<uuid:account_id>/unlock",
        StaffAccountUnlockView.as_view(),
        name="staff-accounts-unlock",
    ),
]
