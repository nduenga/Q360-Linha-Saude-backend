from django.urls import path

from .views import (
    CatalogView,
    ConfigurationApproveView,
    ConfigurationDetailView,
    ConfigurationListCreateView,
    DocumentDownloadView,
    DocumentListView,
    DocumentUploadView,
)

urlpatterns = [
    path("business-config/catalog", CatalogView.as_view()),
    path("business-config/configurations", ConfigurationListCreateView.as_view()),
    path("business-config/configurations/<uuid:configuration_id>", ConfigurationDetailView.as_view()),
    path("business-config/configurations/<uuid:configuration_id>/approve", ConfigurationApproveView.as_view()),
    path("business-config/configurations/<uuid:configuration_id>/documents", DocumentListView.as_view()),
    path("business-config/configurations/<uuid:configuration_id>/documents/upload", DocumentUploadView.as_view()),
    path("business-config/documents/<uuid:document_id>/download", DocumentDownloadView.as_view()),
]
