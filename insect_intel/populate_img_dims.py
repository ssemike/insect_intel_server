import os
import django
from PIL import Image

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'insect_intel.settings')
django.setup()

from insect_intel_server.models import DeviceImage

def populate_dimensions():
    images = DeviceImage.objects.filter(width__isnull=True)
    print(f"Found {images.count()} images to process.")
    
    for img in images:
        try:
            if img.image_file and os.path.exists(img.image_file.path):
                with Image.open(img.image_file.path) as pil_img:
                    img.width, img.height = pil_img.size
                    img.save()
                    print(f"Updated image {img.id}: {img.width}x{img.height}")
            else:
                print(f"File missing for image {img.id}")
        except Exception as e:
            print(f"Error processing image {img.id}: {e}")

if __name__ == "__main__":
    populate_dimensions()
