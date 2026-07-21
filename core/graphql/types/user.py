from graphene_django import DjangoObjectType
from core.models import User, NotificationPreference
import graphene
from .role import RoleType, PermissionType
from django.contrib.auth.models import Permission

class UserType(DjangoObjectType):
    roles = graphene.List(RoleType)
    permissions = graphene.List(PermissionType)

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "phone", "user_type", "assigned_area")

    def resolve_roles(self, info):
        return self.groups.all()

    def resolve_permissions(self, info):
        # Returns specific user permissions + permissions inherited from groups
        if self.is_superuser:
            return Permission.objects.all()
        return self.user_permissions.all() | \
               Permission.objects.filter(group__user=self)

class NotificationPreferenceType(DjangoObjectType):
    class Meta:
        model = NotificationPreference
        fields = "__all__"
