from django.urls import path
from .views import (
    landing_page_view,
    view_raw_body,
    SimpleUploadView,
    view_uploads,
    view_upload_detail,
    download_upload,
    delete_upload,
    # Phase 2
    DiagnosticUploadView,
    DeviceImageUploadView,
    dashboard_view,
    device_list_view,
    device_detail_view,
    diagnostic_list_view,
    diagnostic_detail_view,
    image_gallery_view,
    device_configure_view,
    delete_diagnostic_cascade_view,
    delete_image_cascade_view,
    TimeAPIView
)

urlpatterns = [
    path('', landing_page_view, name='landing'),
    path('upload/', SimpleUploadView.as_view(), name='upload'),
    path('debug/raw-body/', view_raw_body, name='view_raw_body'),

    # Existing view endpoints
    path('uploads/', view_uploads, name='view_uploads'),
    path('uploads/<int:upload_id>/', view_upload_detail, name='upload_detail'),
    path('uploads/<int:upload_id>/download/', download_upload, name='download_upload'),
    path('uploads/<int:upload_id>/delete/', delete_upload, name='delete_upload'),

    # Phase 2 API Endpoints
    path('diagnostics/upload/', DiagnosticUploadView.as_view(), name='diagnostic_upload'),
    path('images/upload/', DeviceImageUploadView.as_view(), name='image_upload'),
    path('api/time/', TimeAPIView.as_view(), name='time_api'),

    # Phase 2 Dashboard Views
    path('dashboard/', dashboard_view, name='dashboard'),
    path('devices/', device_list_view, name='device_list'),
    path('devices/<str:device_id>/', device_detail_view, name='device_detail'),
    path('diagnostics/', diagnostic_list_view, name='diagnostic_list'),
    path('diagnostics/<int:diag_id>/', diagnostic_detail_view, name='diagnostic_detail'),
    path('gallery/', image_gallery_view, name='image_gallery'),

    # Configuration & Commands
    path('devices/<str:device_id>/configure/', device_configure_view, name='device_configure'),
    
    # Deletions
    path('diagnostics/<int:diag_id>/delete/', delete_diagnostic_cascade_view, name='delete_diagnostic_cascade'),
    path('images/<int:img_id>/delete/', delete_image_cascade_view, name='delete_image_cascade'),

]

