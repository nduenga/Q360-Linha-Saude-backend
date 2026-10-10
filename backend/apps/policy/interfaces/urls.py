from django.urls import path

from apps.policy.interfaces.coverage_views import CoverageLookupView, PolicyCoverageView
from apps.policy.interfaces.member_document_views import (
    MemberDocumentDownloadView,
    MemberDocumentListCreateView,
    MemberDocumentQueueView,
    MemberDocumentReviewView,
)
from apps.policy.interfaces.views import (
    EmitPolicyView,
    InstallmentListView,
    PolicyDocumentView,
    PolicyDraftView,
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
    path("quotes/<uuid:quote_id>/policy-draft", PolicyDraftView.as_view(), name="policy-draft"),
    path("quotes/<uuid:quote_id>/policy/emit", EmitPolicyView.as_view(), name="policy-emit"),
    path("policies/<uuid:policy_id>/document", PolicyDocumentView.as_view(), name="policy-document"),
    path("coverage", CoverageLookupView.as_view(), name="coverage-lookup"),
    path("members/<uuid:member_id>/documents", MemberDocumentListCreateView.as_view(), name="member-documents"),
    path("member-documents", MemberDocumentQueueView.as_view(), name="member-document-queue"),
    path("member-documents/<uuid:document_id>/download", MemberDocumentDownloadView.as_view(), name="member-document-download"),
    path("member-documents/<uuid:document_id>/review", MemberDocumentReviewView.as_view(), name="member-document-review"),
    path("installments", InstallmentListView.as_view(), name="installment-list"),
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
