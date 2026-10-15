from django.urls import path

from apps.eligibility.interfaces.views import (
    EligibilityEvaluateView,
    EligibilityExecutionDetailView,
    EligibilityExecutionListView,
)


urlpatterns = [
    path("eligibility/evaluate", EligibilityEvaluateView.as_view(), name="eligibility-evaluate"),
    path(
        "eligibility/evaluations",
        EligibilityExecutionListView.as_view(),
        name="eligibility-execution-list",
    ),

    path(
        "eligibility/evaluations/<uuid:evaluation_id>",
        EligibilityExecutionDetailView.as_view(),
        name="eligibility-execution-detail",
    ),

]
