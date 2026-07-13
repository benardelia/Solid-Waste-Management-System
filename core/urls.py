from django.urls import path
from . import views


# URLConf
urlpatterns = [
    path("users/", views.user_list),
    path("user/<int:id>/", views.user_detail),
    path("user/me/", views.who_ami)
]
