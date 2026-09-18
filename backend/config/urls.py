"""Root URL configuration for the Q360 backend."""
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

urlpatterns = [
    path("api/v1/", include("apps.foundation.interfaces.urls")),
    path("api/v1/", include("apps.product.interfaces.urls")),
    path("api/v1/", include("apps.client.interfaces.urls")),
    path("api/v1/", include("apps.eligibility.interfaces.urls")),
    path("api/v1/", include("apps.pricing.interfaces.urls")),
    path("api/v1/", include("apps.quote.interfaces.urls")),
    path("api/v1/schema", SpectacularAPIView.as_view(), name="openapi-schema"),
]
