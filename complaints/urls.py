from django.urls import path

from .views import ComplaintPhotoView

urlpatterns = [
    path('<int:pk>/photo/', ComplaintPhotoView.as_view(), name='complaint-photo'),
]
