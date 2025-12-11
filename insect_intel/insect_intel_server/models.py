from django.db import models

class RawFrameUpload(models.Model):
    # The file path should also change to reflect that it's raw data
    raw_file = models.FileField(upload_to='raw_frames/%Y/%m/%d/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    device_id = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"Raw frame from {self.device_id} at {self.uploaded_at.isoformat()}"