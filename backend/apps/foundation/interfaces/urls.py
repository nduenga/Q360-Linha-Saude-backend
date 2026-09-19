from django.urls import path

from apps.foundation.interfaces.auth_views import DevLoginView
from apps.foundation.interfaces.rule_views import RuleVersionCreateView
from apps.foundation.interfaces.views import AuditEventListView, LiveHealthView, MeView, ReadyHealthView

urlpatterns = [
    # No trailing slash: ART-006 defines the path as exactly `/api/v1/me`.
    path("me", MeView.as_view(), name="me"),
    path("auth/dev-login", DevLoginView.as_view(), name="auth-dev-login"),
    path("rule-versions", RuleVersionCreateView.as_view(), name="rule-version-create"),
    path("audit-events", AuditEventListView.as_view(), name="audit-event-list"),
    path("health/live", LiveHealthView.as_view(), name="health-live"),
    path("health/ready", ReadyHealthView.as_view(), name="health-ready"),
]
