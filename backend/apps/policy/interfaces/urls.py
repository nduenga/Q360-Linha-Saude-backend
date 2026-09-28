from django.urls import path

from apps.policy.interfaces.coverage_views import CoverageLookupView, PolicyCoverageView
from apps.policy.interfaces.views import (
    IssuePolicyView,
    PolicyDetailView,
    PolicyInstallmentListView,
    PolicyListView,
    PolicyMemberListView,
    PolicySignatureView,
    RegisterFirstPremiumPaymentView,
)

urlpatterns = [
    path("quotes/<uuid:quote_id>/policy", IssuePolicyView.as_view(), name="policy-issue"),
    path("coverage", CoverageLookupView.as_view(), name="coverage-lookup"),
    path("policies", PolicyListView.as_view(), name="policy-list"),
    path("policies/<uuid:policy_id>", PolicyDetailView.as_view(), name="policy-detail"),
    path("policies/<uuid:policy_id>/members", PolicyMemberListView.as_view(), name="policy-member-list"),
    path("policies/<uuid:policy_id>/coverage", PolicyCoverageView.as_view(), name="policy-coverage"),
    path("policies/<uuid:policy_id>/signature", PolicySignatureView.as_view(), name="policy-signature"),
    path(
        "policies/<uuid:policy_id>/installments",
        PolicyInstallmentListView.as_view(),
        name="policy-installment-list",
    ),
    path(
        "policies/<uuid:policy_id>/installments/<int:installment_no>/payment",
        RegisterFirstPremiumPaymentView.as_view(),
        name="policy-installment-payment",
    ),
]
