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
from rest_framework.parsers import MultiPartParser, FormParser, FileUploadParser
import os

from .models import RawFrameUpload, DeviceDiagnostic, DeviceImage, DeviceCommand
from django.utils import timezone
from datetime import datetime, timedelta
import json
import pytz



# -------------------------------------------------
# Helpers
# -------------------------------------------------

from rest_framework.parsers import BaseParser

class OctetStreamParser(BaseParser):
    media_type = 'application/octet-stream'

    def parse(self, stream, media_type=None, parser_context=None):
        return stream.read()

def parse_device_timestamp(filename):
    """
    Parses timestamps from filename. Supports:
    - YYYYMMDDHHMM (12 digits)
    - YYYYMMDDHHMMSS (14 digits)
    - Separators like - or _ (e.g., 2026-01-13_13-30-05)
    Returns a timezone-aware datetime object or None if parsing fails.
    """
    if not filename:
        return None
        
    import re
    # Try 14 digits first (with seconds)
    match_14 = re.search(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})', filename)
    if match_14:
        try:
            ts_str = "".join(match_14.groups())
            naive_dt = datetime.strptime(ts_str, "%Y%m%d%H%M%S")
            return timezone.make_aware(naive_dt, pytz.UTC)
        except (ValueError, TypeError):
            pass

    # Try 12 digits (no seconds)
    match_12 = re.search(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_]?(\d{2})', filename)
    if match_12:
        try:
            ts_str = "".join(match_12.groups())
            naive_dt = datetime.strptime(ts_str, "%Y%m%d%H%M")
            return timezone.make_aware(naive_dt, pytz.UTC)
        except (ValueError, TypeError):
            pass

    return None

def decode_wifi_filename(filename):
    """
    Decodes WiFi module filename encoding.
    The module cannot send dots in URL params, so extensions
    are encoded as __ext__ and need to be converted back to .ext
    
    Examples:
        202604221645__jpg__   -> 202604221645.jpg
        image1__png__         -> image1.png
        frame__bin__          -> frame.bin
    """
    import re
    return re.sub(r'__(\w+)__$', r'.\1', filename)

# -------------------------------------------------
# Utility: Time API
# -------------------------------------------------

class TimeAPIView(APIView):
    """
    Returns current server time for device synchronization.
    """
    permission_classes = [AllowAny]

    def get(self, request, format=None):
        now = timezone.now()
        return Response({
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "hour": now.hour,
            "minute": now.minute,
            "second": now.second,
            "timezone": "UTC"
        }, status=status.HTTP_200_OK)


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

        device_timestamp = parse_device_timestamp(uploaded_file.name)

        upload = RawFrameUpload.objects.create(
            raw_file=uploaded_file,
            device_id=device_id,
            device_timestamp=device_timestamp
        )

        # NEW: auto-linking logic
        link_to_diagnostic(upload)

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
# Phase 2: Structured Telemetry & Image Endpoints
# -------------------------------------------------

class DiagnosticUploadView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, format=None):
        """
        Expected nested JSON payload:
        - MSP0: battery/charger telemetry + config
        - STM: connectivity/system info
        - device_id: unit identity
        - Date: YYYYMMDDHHMM
        """
        data = request.data
        device_id = data.get("device_id") or request.headers.get("X-Device-ID") or "UNKNOWN_DEVICE"
        
        # Split payload components
        mspm0 = data.get("MSPM0", {})
        stm = data.get("STM", {})
        
        # Parse Device Date
        date_str = data.get("Date")
        device_dt = None
        if date_str:
            try:
                naive_dt = datetime.strptime(date_str, "%Y%m%d%H%M")
                device_dt = timezone.make_aware(naive_dt, pytz.UTC)
            except (ValueError, TypeError):
                pass

        # 1. Check for command confirmation
        confirmed_id = mspm0.get("confirmed_command_id") or data.get("confirmed_command_id")
        if confirmed_id:
            DeviceCommand.objects.filter(id=confirmed_id, device_id=device_id, status='SENT').update(status='COMPLETED')

        # 2. Create diagnostic record
        diagnostic = DeviceDiagnostic.objects.create(
            device_id=device_id,
            device_timestamp=device_dt,
            raw_payload=data,
            # MSPM0 Telemetry
            soc=mspm0.get("soc"),
            soh=mspm0.get("soh"),
            cycles=mspm0.get("cycles"),
            lowbattery=bool(mspm0.get("lowbattery", False)),
            vbat=mspm0.get("vbat"),
            ibat=mspm0.get("ibat"),
            vchg=mspm0.get("vchg"),
            vsys=mspm0.get("vsys"),
            ichg=mspm0.get("ichg"),
            avgi=mspm0.get("avgi"),
            avgpwr=mspm0.get("avgpwr"),
            gtmp=mspm0.get("gtmp"),
            ctmp=mspm0.get("ctmp"),
            btmp=mspm0.get("btmp"),
            state=mspm0.get("state"),
            wake=mspm0.get("wake"),
            adapter=bool(mspm0.get("adapter", False)),
            safety=mspm0.get("safety"),
            battstat=mspm0.get("battstat"),
            chgflags=mspm0.get("chgflags"),
            faultflags=mspm0.get("faultflags"),
            chgstat=mspm0.get("chgstat"),
            # MSPM0 Config Snapshot
            cfg_wake_interval=mspm0.get("wake_interval"),
            cfg_vreg=mspm0.get("vreg"),
            cfg_ichg=mspm0.get("cfg_ichg"),
            cfg_iindpm=mspm0.get("iindpm"),
            cfg_vindpm=mspm0.get("vindpm"),
            cfg_vsysmin=mspm0.get("vsysmin"),
            cfg_iprechg=mspm0.get("iprechg"),
            cfg_iterm=mspm0.get("iterm"),
            # STM Connectivity
            lte_stat=stm.get("lte_stat"),
            lte_sig=stm.get("lte_sig"),
            sim_pres=bool(stm.get("sim_pres", False)),
            sim_num=stm.get("sim_num"),
            net=stm.get("net"),
            wifi_stat=stm.get("wifi_stat"),
            last_comm_epoch=stm.get("last_comm"),
            sd_pres=bool(stm.get("sd_pres", False)),
            sd_free=stm.get("sd_free"),
            lte_sent=stm.get("lte_sent"),
            cam_res=stm.get("cam_res"),
        )

        perform_retroactive_linking(diagnostic)

        # 3. Check for pending commands
        response_data = {
            "message": "Diagnostic received",
            "id": diagnostic.id,
            "device_id": device_id,
            "timestamp_linked": bool(device_dt)
        }

        pending_command = DeviceCommand.objects.filter(device_id=device_id, status='PENDING').order_by('-created_at').first()
        if pending_command:
            now = timezone.now()
            payload = pending_command.payload
            
            response_data["configuration"] = {
                "command_id": pending_command.id,
                "rtc": {
                    "year": now.year,
                    "month": now.month,
                    "day": now.day,
                    "hour": now.hour,
                    "minute": now.minute,
                    "second": now.second,
                    "wake_interval_minutes": payload.get("wake_interval_minutes", 10)
                },
                "charger": {
                    "vreg_mV": payload.get("vreg_mV", 4200),
                    "ichg_mA": payload.get("ichg_mA", 500),
                    "iindpm_mA": payload.get("iindpm_mA", 1500),
                    "vindpm_mV": payload.get("vindpm_mV", 4500),
                    "vsysmin_mV": payload.get("vsysmin_mV", 3500),
                    "iprechg_mA": payload.get("iprechg_mA", 50),
                    "iterm_mA": payload.get("iterm_mA", 50)
                }
            }
            pending_command.status = 'SENT'
            pending_command.save()

        return Response(response_data, status=status.HTTP_201_CREATED)


class DeviceImageUploadView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [OctetStreamParser, MultiPartParser, FormParser]

    def post(self, request, format=None):
        uploaded_file = None


        if isinstance(request.data, bytes) and request.data:
            from django.core.files.uploadedfile import InMemoryUploadedFile
            import io
            
            # Use filename from query params if available, else a default
            fname = request.query_params.get("filename", "upload.bin")
            
            uploaded_file = InMemoryUploadedFile(
                file=io.BytesIO(request.data),
                field_name="file",
                name=fname,
                content_type="application/octet-stream",
                size=len(request.data),
                charset=None
            )

        if not uploaded_file:
            uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            return Response({
                "error": "No file content detected.",
                "debug_data_type": str(type(request.data)),
            }, status=status.HTTP_400_BAD_REQUEST)

        device_id = (
            request.POST.get("device_id")            # LTE multipart form field
            or request.query_params.get("deviceId")  # WiFi URL param
            or request.headers.get("X-Device-ID")    # Either via header
            or "UNKNOWN_DEVICE"
        )

        if not hasattr(uploaded_file, 'name') or not uploaded_file.name:
            url_filename = request.query_params.get("filename")
            if url_filename:
                uploaded_file.name = decode_wifi_filename(url_filename)
            else:
                uploaded_file.name = f"upload_{timezone.now().strftime('%Y%m%d%H%M%S')}.bin"
        else:
            # Also decode existing name if it came from octet-stream block
            uploaded_file.name = decode_wifi_filename(uploaded_file.name)

        device_timestamp = parse_device_timestamp(uploaded_file.name)

        image = DeviceImage.objects.create(
            image_file=uploaded_file,
            device_id=device_id,
            device_timestamp=device_timestamp
        )

        link_to_diagnostic(image)

        return Response({
            "message": "Image received successfully",
            "id": image.id,
            "device_id": device_id,
            "filename": uploaded_file.name,
            "parser_used": request.content_type
        }, status=status.HTTP_201_CREATED)


# -------------------------------------------------
# Internal Linking Logic
# -------------------------------------------------

def link_to_diagnostic(instance):
    """
    Search for a DeviceDiagnostic record from the same device.
    Prioritizes exact match on device_timestamp (firmware time).
    Falls back to ±60s window on uploaded_at (server reception time).
    """
    # 1. Try exact timestamp match first (The new reliable way)
    if instance.device_timestamp:
        diagnostic = DeviceDiagnostic.objects.filter(
            device_id=instance.device_id,
            device_timestamp=instance.device_timestamp
        ).first()
        if diagnostic:
            instance.linked_diagnostic = diagnostic
            instance.save()
            return

    # 2. Fallback to temporal proximity window
    time_window = timedelta(seconds=60)
    anchor_time = instance.uploaded_at or timezone.now()
    
    diagnostic = DeviceDiagnostic.objects.filter(
        device_id=instance.device_id,
        received_at__range=(anchor_time - time_window, anchor_time + time_window)
    ).order_by('received_at').first()

    if diagnostic:
        instance.linked_diagnostic = diagnostic
        instance.save()


def perform_retroactive_linking(diagnostic):
    """
    When a diagnostic arrives, check for orphaned media.
    Matches by device_timestamp first, then falls back to uploaded_at window.
    """
    # 1. Match by exact device_timestamp
    if diagnostic.device_timestamp:
        RawFrameUpload.objects.filter(
            device_id=diagnostic.device_id,
            device_timestamp=diagnostic.device_timestamp,
            linked_diagnostic__isnull=True
        ).update(linked_diagnostic=diagnostic)

        DeviceImage.objects.filter(
            device_id=diagnostic.device_id,
            device_timestamp=diagnostic.device_timestamp,
            linked_diagnostic__isnull=True
        ).update(linked_diagnostic=diagnostic)

    # 2. Fallback to window-based linking for orphans still unlinked
    time_window = timedelta(seconds=60)
    start_time = diagnostic.received_at - time_window
    end_time = diagnostic.received_at + time_window

    RawFrameUpload.objects.filter(
        device_id=diagnostic.device_id,
        linked_diagnostic__isnull=True,
        uploaded_at__range=(start_time, end_time)
    ).update(linked_diagnostic=diagnostic)

    DeviceImage.objects.filter(
        device_id=diagnostic.device_id,
        linked_diagnostic__isnull=True,
        uploaded_at__range=(start_time, end_time)
    ).update(linked_diagnostic=diagnostic)



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
# Dashboard Views
# -------------------------------------------------

def dashboard_view(request):
    """Main dashboard with summary analytics"""
    devices = DeviceDiagnostic.objects.values('device_id').distinct()
    recent_diagnostics = DeviceDiagnostic.objects.all().order_by('-received_at')[:10]
    recent_images = DeviceImage.objects.all().order_by('-uploaded_at')[:8]
    
    context = {
        'device_count': devices.count(),
        'diagnostic_count': DeviceDiagnostic.objects.count(),
        'image_count': DeviceImage.objects.count(),
        'recent_diagnostics': recent_diagnostics,
        'recent_images': recent_images,
    }
    return render(request, 'dashboard.html', context)


def device_list_view(request):
    """List of unique devices and their last status"""
    from django.db.models import Max, OuterRef, Subquery
    
    # Subquery to get the latest diagnostic for each device
    latest_diag_ids = DeviceDiagnostic.objects.filter(
        device_id=OuterRef('device_id')
    ).order_by('-received_at').values('id')[:1]

    # Distinct device list with their latest status
    device_stats = DeviceDiagnostic.objects.filter(
        id__in=Subquery(latest_diag_ids)
    ).order_by('-received_at')

    return render(request, 'device_list.html', {'devices': device_stats})


def device_detail_view(request, device_id):
    """Detailed view for a specific device (charts + images)"""
    diagnostics = DeviceDiagnostic.objects.filter(device_id=device_id).order_by('-received_at')
    images = DeviceImage.objects.filter(device_id=device_id).order_by('-uploaded_at')[:20]
    
    # Prepare data for Chart.js (last 20 points)
    chart_data = list(diagnostics.order_by('received_at')[:20].values('received_at', 'soc', 'vbat', 'btmp'))
    
    return render(request, 'device_detail.html', {
        'device_id': device_id,
        'diagnostics': diagnostics[:50],
        'images': images,
        'chart_data_json': json.dumps(chart_data, default=str),
        'latest': diagnostics.first()
    })


def diagnostic_list_view(request):
    """Paginated list of all diagnostics"""
    diags = DeviceDiagnostic.objects.all().order_by('-received_at')
    paginator = Paginator(diags, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'diagnostic_list.html', {'page_obj': page_obj})


def diagnostic_detail_view(request, diag_id):
    """Full breakdown of a single diagnostic record"""
    diag = get_object_or_404(DeviceDiagnostic, id=diag_id)
    return render(request, 'diagnostic_detail.html', {'diag': diag})


def image_gallery_view(request):
    """Full gallery of all uploaded images"""
    images = DeviceImage.objects.all().order_by('-uploaded_at')
    paginator = Paginator(images, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'image_gallery.html', {'page_obj': page_obj})



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
        'file_size': upload.raw_file.size if upload.raw_file else 0,
        'linked_diagnostic': upload.linked_diagnostic
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
def device_configure_view(request, device_id):
    """View to queue a configuration command for a device"""
    if request.method == 'POST':
        payload = {
            "wake_interval_minutes": int(request.POST.get("wake_interval_minutes", 10)),
            "vreg_mV": int(request.POST.get("vreg_mV", 4200)),
            "ichg_mA": int(request.POST.get("ichg_mA", 50)),
            "iindpm_mA": int(request.POST.get("iindpm_mA", 1500)),
            "vindpm_mV": int(request.POST.get("vindpm_mV", 4500)),
            "vsysmin_mV": int(request.POST.get("vsysmin_mV", 3500)),
            "iprechg_mA": int(request.POST.get("iprechg_mA", 50)),
            "iterm_mA": int(request.POST.get("iterm_mA", 50)),
        }
        
        DeviceCommand.objects.create(
            device_id=device_id,
            command_type='CONFIG',
            payload=payload,
            status='PENDING'
        )
        messages.success(request, f"Configuration command queued for {device_id}.")
        return redirect('device_detail', device_id=device_id)

    # Get the latest config or defaults
    latest_cmd = DeviceCommand.objects.filter(device_id=device_id, command_type='CONFIG').order_by('-created_at').first()
    latest_diag = DeviceDiagnostic.objects.filter(device_id=device_id).order_by('-received_at').first()
    
    context = {
        'device_id': device_id,
        'config': latest_cmd.payload if latest_cmd else {},
        'current': latest_diag
    }
    return render(request, 'device_configure.html', context)


def delete_diagnostic_cascade_view(request, diag_id):
    """Delete a diagnostic and all its related media (images/frames)"""
    diag = get_object_or_404(DeviceDiagnostic, id=diag_id)
    device_id = diag.device_id
    
    # Delete related images and their files
    for img in diag.images.all():
        if img.image_file and os.path.exists(img.image_file.path):
            os.remove(img.image_file.path)
        img.delete()
        
    # Delete related raw frames and their files
    for frame in diag.raw_frames.all():
        if frame.raw_file and os.path.exists(frame.raw_file.path):
            os.remove(frame.raw_file.path)
        frame.delete()
        
    # Delete the diagnostic itself
    diag.delete()
    
    messages.success(request, f"Diagnostic #{diag_id} and all related media deleted.")
    return redirect('diagnostic_list')


def delete_image_cascade_view(request, img_id):
    """Delete an image and its linked diagnostic (if it exists)"""
    img = get_object_or_404(DeviceImage, id=img_id)
    device_id = img.device_id
    diag = img.linked_diagnostic
    
    # Delete image file
    if img.image_file and os.path.exists(img.image_file.path):
        os.remove(img.image_file.path)
    img.delete()
    
    # If there's a linked diagnostic, delete it too (and other media linked to it)
    if diag:
        # Re-use the cascade logic
        for other_img in diag.images.all():
            if other_img.image_file and os.path.exists(other_img.image_file.path):
                os.remove(other_img.image_file.path)
            other_img.delete()
            
        for frame in diag.raw_frames.all():
            if frame.raw_file and os.path.exists(frame.raw_file.path):
                os.remove(frame.raw_file.path)
            frame.delete()
            
        diag.delete()
        messages.success(request, f"Image #{img_id} and its associated diagnostic session deleted.")
    else:
        messages.success(request, f"Image #{img_id} deleted.")
        
    return redirect('device_detail', device_id=device_id)
