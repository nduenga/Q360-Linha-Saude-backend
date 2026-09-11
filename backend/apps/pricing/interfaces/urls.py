from django.urls import path

from apps.pricing.interfaces.views import RatingTableCreateView

urlpatterns = [
    path("rating-tables", RatingTableCreateView.as_view(), name="rating-table-create"),
]
