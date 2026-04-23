from django.contrib import admin
from . import models

@admin.register(models.RawFrameUpload)
class RawFrameUploadAdmin(admin.ModelAdmin):
    list_display = ['uploaded_at','device_id']
    list_editable = ['device_id']
    search_fields = ['device_id']
