from django.urls import path
from .views import (
    landing_page_view,
    view_raw_body,
    SimpleUploadView,
    view_uploads,
    view_upload_detail,
    download_upload,
    delete_upload
)

urlpatterns = [
    path('', landing_page_view, name='landing'),
    path('upload/', SimpleUploadView.as_view(), name='upload'),
    path('debug/raw-body/', view_raw_body, name='view_raw_body'),

    # New view endpoints
    path('uploads/', view_uploads, name='view_uploads'),
    path('uploads/<int:upload_id>/', view_upload_detail, name='upload_detail'),
    path('uploads/<int:upload_id>/download/', download_upload, name='download_upload'),
    path('uploads/<int:upload_id>/delete/', delete_upload, name='delete_upload'),

]
