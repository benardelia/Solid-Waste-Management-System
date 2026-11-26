from django.urls import path

from .views import ReportExportView, ReportListView

urlpatterns = [
    path('', ReportListView.as_view(), name='report-list'),
    path('<slug:key>/export/', ReportExportView.as_view(), name='report-export'),
]
