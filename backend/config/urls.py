"""Root URL configuration for the Q360 backend."""
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/v1/", include("apps.foundation.interfaces.urls")),
    path("api/v1/", include("apps.product.interfaces.urls")),
    path("api/v1/", include("apps.client.interfaces.urls")),
    path("api/v1/", include("apps.eligibility.interfaces.urls")),
    path("api/v1/", include("apps.pricing.interfaces.urls")),
    path("api/v1/", include("apps.quote.interfaces.urls")),
    path("api/v1/", include("apps.policy.interfaces.urls")),
    path("api/v1/", include("apps.claims.interfaces.urls")),
    path("api/v1/", include("apps.customer_portal.interfaces.urls")),
    path("api/v1/", include("apps.staff_accounts.interfaces.urls")),
    path("api/v1/", include("apps.business_config.interfaces.urls")),
    path("api/v1/schema", SpectacularAPIView.as_view(), name="openapi-schema"),
    # Debug-only, as-implemented schema browser — NOT the contract (see
    # SPECTACULAR_SETTINGS in config/settings/base.py). ART-006 remains
    # authoritative for the frontend's generated API client.
    path("api/docs", SpectacularSwaggerView.as_view(url_name="openapi-schema"), name="swagger-ui"),
]
