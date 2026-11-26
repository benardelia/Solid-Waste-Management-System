from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ComplaintUpdate
from .services import visible_complaints

MAX_PHOTO_BYTES = 5 * 1024 * 1024


class ComplaintPhotoView(APIView):
    """POST multipart `photo` to attach a picture (GraphQL has no file upload here)."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request, pk):
        complaint = visible_complaints(request.user).filter(pk=pk).first()
        if complaint is None:
            return Response({'detail': 'Complaint not found'}, status=404)
        photo = request.FILES.get('photo')
        if photo is None:
            return Response({'detail': 'Send the image in a "photo" field'}, status=400)
        if photo.size > MAX_PHOTO_BYTES:
            return Response({'detail': 'Photo must be 5 MB or smaller'}, status=400)
        if not (photo.content_type or '').startswith('image/'):
            return Response({'detail': 'Only image files are allowed'}, status=400)
        complaint.photo = photo
        complaint.save(update_fields=['photo', 'updated_at'])
        ComplaintUpdate.objects.create(complaint=complaint, author=request.user, message='Photo attached')
        return Response({'photoUrl': request.build_absolute_uri(complaint.photo.url)})
