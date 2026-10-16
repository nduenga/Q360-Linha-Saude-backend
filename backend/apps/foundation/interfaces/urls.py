from django.urls import path

from apps.foundation.interfaces.auth_views import DevLoginView
from apps.foundation.interfaces.reference_table_views import ReferenceTableDetailView, ReferenceTableListView
from apps.foundation.interfaces.rule_views import RuleVersionCreateView, RuleVersionDetailView
from apps.foundation.interfaces.system_parameter_views import (
    SystemParameterDetailView,
    SystemParameterListView,
    SystemParameterRevisionsView,
    SystemParameterRollbackView,
)
from apps.foundation.interfaces.views import AuditEventListView, DashboardView, LiveHealthView, MeView, ReadyHealthView

urlpatterns = [
    # No trailing slash: ART-006 defines the path as exactly `/api/v1/me`.
    path("me", MeView.as_view(), name="me"),
    path("auth/dev-login", DevLoginView.as_view(), name="auth-dev-login"),
    path("rule-versions", RuleVersionCreateView.as_view(), name="rule-version-create"),
    path("rule-versions/<uuid:rule_version_id>", RuleVersionDetailView.as_view(), name="rule-version-detail"),
    path("audit-events", AuditEventListView.as_view(), name="audit-event-list"),
    path("system-parameters", SystemParameterListView.as_view(), name="system-parameter-list"),
    path("system-parameters/<str:code>", SystemParameterDetailView.as_view(), name="system-parameter-detail"),
    path("system-parameters/<str:code>/revisions", SystemParameterRevisionsView.as_view(), name="system-parameter-revisions"),
    path("system-parameters/<str:code>/rollback", SystemParameterRollbackView.as_view(), name="system-parameter-rollback"),
    path("reference-tables", ReferenceTableListView.as_view(), name="reference-table-list"),
    path("reference-tables/<str:code>", ReferenceTableDetailView.as_view(), name="reference-table-detail"),
    path("dashboard", DashboardView.as_view(), name="dashboard"),
    path("health/live", LiveHealthView.as_view(), name="health-live"),
    path("health/ready", ReadyHealthView.as_view(), name="health-ready"),
]
