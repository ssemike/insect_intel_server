from django.contrib import admin
from . import models

@admin.register(models.RawFrameUpload)
class RawFrameUploadAdmin(admin.ModelAdmin):
    list_display = ['uploaded_at', 'device_id', 'linked_diagnostic']
    search_fields = ['device_id']

@admin.register(models.DeviceDiagnostic)
class DeviceDiagnosticAdmin(admin.ModelAdmin):
    list_display = ['received_at', 'device_id', 'soc', 'vbat', 'lte_sig']
    list_filter = ['device_id', 'received_at']
    search_fields = ['device_id']

@admin.register(models.DeviceImage)
class DeviceImageAdmin(admin.ModelAdmin):
    list_display = ['uploaded_at', 'device_id', 'linked_diagnostic', 'width', 'height']
    list_filter = ['device_id', 'uploaded_at']
    search_fields = ['device_id']

@admin.register(models.DeviceCommand)
class DeviceCommandAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'device_id', 'command_type', 'status']
    list_filter = ['status', 'command_type']
    search_fields = ['device_id']

@admin.register(models.UploadLog)
class UploadLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'upload_type', 'device_id', 'success', 'status_code']
    list_filter = ['success', 'upload_type', 'timestamp']
    search_fields = ['device_id', 'error_message', 'filename']
    readonly_fields = ['timestamp']
