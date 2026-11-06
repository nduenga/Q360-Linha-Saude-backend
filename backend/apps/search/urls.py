from django.urls import path
from apps.search.interfaces.views import GlobalSearchView
from apps.search.interfaces.work_views import StatusDictionaryView, WorkQueueView

urlpatterns = [
    path('search', GlobalSearchView.as_view(), name='global-search'),
    path('work-queue', WorkQueueView.as_view(), name='work-queue'),
    path('status-dictionary', StatusDictionaryView.as_view(), name='status-dictionary'),
]