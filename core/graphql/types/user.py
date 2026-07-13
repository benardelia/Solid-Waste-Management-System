from graphene_django import DjangoObjectType
from core.models import User, NotificationPreference

class UserType(DjangoObjectType):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "phone", "user_type", "assigned_area")

class NotificationPreferenceType(DjangoObjectType):
    class Meta:
        model = NotificationPreference
        fields = "__all__"
