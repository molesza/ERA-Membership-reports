from django.contrib import admin
from django.urls import path
from reports.views import (
    UploadView, ReportHistoryView, ReportDetailView, 
    export_report_pdf, CurrentMembersView, download_contact
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', UploadView.as_view(), name='upload'),
    path('history/', ReportHistoryView.as_view(), name='history'),
    path('report/<int:pk>/', ReportDetailView.as_view(), name='report_detail'),
    path('report/<int:pk>/pdf/', export_report_pdf, name='report_pdf'),
    path('current-members/', CurrentMembersView.as_view(), name='current_members'),
    path('download-contact/<str:cell>/', download_contact, name='download_contact'),
]
