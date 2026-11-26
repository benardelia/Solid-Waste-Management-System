from graphene_django import DjangoObjectType
from core.models import User, NotificationPreference
from core.roles import ROLE_CHOICES, user_role
import graphene
from .role import RoleType, PermissionType
from django.contrib.auth.models import Permission


class UserType(DjangoObjectType):
    roles = graphene.List(RoleType)
    permissions = graphene.List(PermissionType)
    full_name = graphene.String()
    role_label = graphene.String()
    effective_role = graphene.String(description='user_type, or "admin" for superusers')

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "first_name", "last_name", "phone", "user_type", "assigned_area",
            "is_active", "date_joined", "last_login", "firebase_uid",
        )
        convert_choices_to_enum = False

    def resolve_roles(self, info):
        return self.groups.all()

    def resolve_permissions(self, info):
        # Returns specific user permissions + permissions inherited from groups
        if self.is_superuser:
            return Permission.objects.all()
        return self.user_permissions.all() | \
               Permission.objects.filter(group__user=self)

    def resolve_full_name(self, info):
        return self.get_full_name() or self.username

    def resolve_role_label(self, info):
        return dict(ROLE_CHOICES).get(self.user_type, self.user_type)

    def resolve_effective_role(self, info):
        return user_role(self)


class NotificationPreferenceType(DjangoObjectType):
    class Meta:
        model = NotificationPreference
        fields = "__all__"
