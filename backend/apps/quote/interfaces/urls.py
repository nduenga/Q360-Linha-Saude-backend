from django.urls import path

from apps.quote.interfaces.views import (
    DocumentTemplateDetailView,
    DocumentTemplateListCreateView,
    DocumentTemplatePublishView,
    DocumentTemplateRetireView,
    QuoteCancelView,
    QuoteDecisionView,
    QuoteDetailView,
    QuoteHistoryView,
    QuoteListCreateView,
    QuoteMemberDetailView,
    QuoteMemberListCreateView,
    QuotePriceView,
    QuoteProposalView,
    QuoteReviewView,
    QuoteSubmitView,
    ReviewQueueView,
)

urlpatterns = [
    path("quotes", QuoteListCreateView.as_view(), name="quote-list-create"),
    path("quotes/<uuid:quote_id>", QuoteDetailView.as_view(), name="quote-detail"),
    path("quotes/<uuid:quote_id>/members", QuoteMemberListCreateView.as_view(), name="quote-member-list-create"),
    path(
        "quotes/<uuid:quote_id>/members/<uuid:member_id>",
        QuoteMemberDetailView.as_view(),
        name="quote-member-detail",
    ),
    path("quotes/<uuid:quote_id>/price", QuotePriceView.as_view(), name="quote-price"),
    path("quotes/<uuid:quote_id>/submit", QuoteSubmitView.as_view(), name="quote-submit"),
    path("quotes/<uuid:quote_id>/review", QuoteReviewView.as_view(), name="quote-review"),
    path("quotes/<uuid:quote_id>/decision", QuoteDecisionView.as_view(), name="quote-decision"),
    path("quotes/<uuid:quote_id>/history", QuoteHistoryView.as_view(), name="quote-history"),
    path("quotes/<uuid:quote_id>/cancel", QuoteCancelView.as_view(), name="quote-cancel"),
    path("quotes/<uuid:quote_id>/proposal", QuoteProposalView.as_view(), name="quote-proposal"),
    path("document-templates", DocumentTemplateListCreateView.as_view(), name="document-template-create"),
    path(
        "document-templates/<uuid:template_id>",
        DocumentTemplateDetailView.as_view(),
        name="document-template-detail",
    ),
    path(
        "document-templates/<uuid:template_id>/publish",
        DocumentTemplatePublishView.as_view(),
        name="document-template-publish",
    ),
    path(
        "document-templates/<uuid:template_id>/retire",
        DocumentTemplateRetireView.as_view(),
        name="document-template-retire",
    ),
    path("reviews", ReviewQueueView.as_view(), name="review-queue"),
]
