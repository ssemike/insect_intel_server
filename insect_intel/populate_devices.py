import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'insect_intel.settings')
django.setup()

from insect_intel_server.models import Device, DeviceDiagnostic

device_ids = DeviceDiagnostic.objects.values_list('device_id', flat=True).distinct()
count = 0
for d_id in device_ids:
    _, created = Device.objects.get_or_create(device_id=d_id)
    if created:
        count += 1
print(f'Populated {count} new devices from existing diagnostics.')
