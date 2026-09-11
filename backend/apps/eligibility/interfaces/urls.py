from django.urls import path

from apps.eligibility.interfaces.views import EligibilityEvaluateView

urlpatterns = [
    path("eligibility/evaluate", EligibilityEvaluateView.as_view(), name="eligibility-evaluate"),
]
