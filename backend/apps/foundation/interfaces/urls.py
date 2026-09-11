from django.urls import path

from apps.foundation.interfaces.rule_views import RuleVersionCreateView
from apps.foundation.interfaces.views import MeView

urlpatterns = [
    # No trailing slash: ART-006 defines the path as exactly `/api/v1/me`.
    path("me", MeView.as_view(), name="me"),
    path("rule-versions", RuleVersionCreateView.as_view(), name="rule-version-create"),
]
