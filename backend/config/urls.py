"""Root URL configuration for the Q360 backend."""
from django.urls import include, path

urlpatterns = [
    path("api/v1/", include("apps.foundation.interfaces.urls")),
    path("api/v1/", include("apps.product.interfaces.urls")),
    path("api/v1/", include("apps.client.interfaces.urls")),
    path("api/v1/", include("apps.eligibility.interfaces.urls")),
]
