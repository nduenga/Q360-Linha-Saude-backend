from django.urls import path

from .views import (
    BCCatalogView,
    BCConfigurationApproveView,
    BCConfigurationDetailView,
    BCConfigurationListCreateView,
    BCDocumentDownloadView,
    BCDocumentListView,
    BCDocumentUploadView,
)

urlpatterns = [
    path("business-config/catalog", BCCatalogView.as_view()),
    path("business-config/configurations", BCConfigurationListCreateView.as_view()),
    path("business-config/configurations/<uuid:configuration_id>", BCConfigurationDetailView.as_view()),
    path("business-config/configurations/<uuid:configuration_id>/approve", BCConfigurationApproveView.as_view()),
    path("business-config/configurations/<uuid:configuration_id>/documents", BCDocumentListView.as_view()),
    path("business-config/configurations/<uuid:configuration_id>/documents/upload", BCDocumentUploadView.as_view()),
    path("business-config/documents/<uuid:document_id>/download", BCDocumentDownloadView.as_view()),
]
