from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from reports.views import (
    UploadView, ReportHistoryView, ReportDetailView, 
    export_report_pdf, CurrentMembersView, download_contact
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='reports/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', UploadView.as_view(), name='upload'),
    path('history/', ReportHistoryView.as_view(), name='history'),
    path('report/<int:pk>/', ReportDetailView.as_view(), name='report_detail'),
    path('report/<int:pk>/pdf/', export_report_pdf, name='report_pdf'),
    path('current-members/', CurrentMembersView.as_view(), name='current_members'),
    path('download-contact/<str:cell>/', download_contact, name='download_contact'),
]
