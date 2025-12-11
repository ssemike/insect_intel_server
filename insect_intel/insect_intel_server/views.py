from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny 
from .models import RawFrameUpload  

class SimpleUploadView(APIView):

    def post(self, request, format=None):
        uploaded_file = request.FILES.get('file')
        device_id = request.POST.get('device_id', 'TEST_ANONYMOUS') 

        if not uploaded_file:
            # Note: The error message is cleaner without the trailing '?'.
            return Response(
                {"error": "File part ('file') is missing or empty."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # This creates the object:
            RawFrameUpload.objects.create(
                raw_file=uploaded_file,
                device_id=device_id 
            )
            

            return Response(
                {"message": "Raw frame received successfully.", "device": device_id}, 
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            # This returns an error Response object:
            return Response(
                {"error": "Server processing failed.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )