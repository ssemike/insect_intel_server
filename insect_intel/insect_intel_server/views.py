from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.contrib import messages
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
import os

from .models import RawFrameUpload


# -------------------------------------------------
# Landing page
# -------------------------------------------------

def landing_page_view(request):
    return render(request, 'landing.html', {})


# -------------------------------------------------
# DEBUG: view raw body exactly as received
# -------------------------------------------------

@csrf_exempt
def view_raw_body(request):
    if request.method != "POST":
        return HttpResponse(
            "POST to this endpoint to see the raw body.",
            content_type="text/plain"
        )

    raw_bytes = request.body or b""
    raw_text = raw_bytes.decode("utf-8", errors="replace")

    return HttpResponse(raw_text, content_type="text/plain")


# -------------------------------------------------
# PRODUCTION: multipart upload endpoint
# -------------------------------------------------

class SimpleUploadView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, format=None):
        """
        Expected multipart fields:
        - file        (required)
        - device_id   (optional)
        """

        uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            return Response(
                {
                    "error": "Missing multipart field 'file'.",
                    "received_files": list(request.FILES.keys())
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        device_id = (
            request.POST.get("device_id")
            or request.headers.get("X-Device-ID")
            or request.headers.get("User-Agent")
            or "UNKNOWN_DEVICE"
        )

        upload = RawFrameUpload.objects.create(
            raw_file=uploaded_file,
            device_id=device_id
        )

        return Response(
            {
                "message": "Raw frame received successfully",
                "upload_id": upload.id,
                "device_id": device_id,
                "filename": uploaded_file.name,
                "size_bytes": uploaded_file.size,
            },
            status=status.HTTP_201_CREATED
        )


# -------------------------------------------------
# View all uploads
# -------------------------------------------------

def view_uploads(request):
    """List all uploaded raw frames with pagination"""
    uploads = RawFrameUpload.objects.all().order_by('-uploaded_at')
    
    # Pagination - 20 items per page
    paginator = Paginator(uploads, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'view_uploads.html', {
        'page_obj': page_obj,
        'total_count': uploads.count()
    })


# -------------------------------------------------
# View individual upload details
# -------------------------------------------------

def view_upload_detail(request, upload_id):
    """View details and content of a specific upload"""
    upload = get_object_or_404(RawFrameUpload, id=upload_id)
    
    content = None
    error = None
    
    try:
        # Read the file content
        raw_content = upload.raw_file.read()
        
        # Try to decode as UTF-8 text
        if isinstance(raw_content, bytes):
            try:
                content = raw_content.decode('utf-8')
            except UnicodeDecodeError:
                # If not UTF-8, show as hex dump
                content = raw_content.hex()
                error = "Binary content (showing hex representation)"
    except Exception as e:
        error = f"Error reading file: {str(e)}"
    
    return render(request, 'upload_detail.html', {
        'upload': upload,
        'content': content,
        'error': error,
        'file_size': upload.raw_file.size if upload.raw_file else 0
    })


# -------------------------------------------------
# Download raw file
# -------------------------------------------------

def download_upload(request, upload_id):
    """Download the raw file"""
    upload = get_object_or_404(RawFrameUpload, id=upload_id)
    
    response = HttpResponse(
        upload.raw_file.read(),
        content_type='application/octet-stream'
    )
    response['Content-Disposition'] = f'attachment; filename="{upload.device_id}_{upload.id}.bin"'
    
    return response


def delete_upload(request, upload_id):
    """Delete a specific upload and its file from disk"""
    upload = get_object_or_404(RawFrameUpload, id=upload_id)
    
    try:
        # Delete the file from disk
        file_path = upload.raw_file.path
        if os.path.exists(file_path):
            os.remove(file_path)

        # Delete the DB record
        upload.delete()

        messages.success(request, f"Upload #{upload_id} deleted successfully.")
    except Exception as e:
        messages.error(request, f"Error deleting upload #{upload_id}: {str(e)}")

    # Redirect back to the uploads list
    return redirect('view_uploads')
