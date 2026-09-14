from django.urls import path

from apps.quote.interfaces.views import (
    QuoteDetailView,
    QuoteListCreateView,
    QuoteMemberDetailView,
    QuoteMemberListCreateView,
    QuotePriceView,
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
]
