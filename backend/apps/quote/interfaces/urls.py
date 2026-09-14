from django.urls import path

from apps.quote.interfaces.views import (
    QuoteDecisionView,
    QuoteDetailView,
    QuoteHistoryView,
    QuoteListCreateView,
    QuoteMemberDetailView,
    QuoteMemberListCreateView,
    QuotePriceView,
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
    path("reviews", ReviewQueueView.as_view(), name="review-queue"),
]
