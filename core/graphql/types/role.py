import graphene
from graphene_django import DjangoObjectType
from django.contrib.auth.models import Group, Permission

class PermissionType(DjangoObjectType):
    class Meta:
        model = Permission
        fields = ("id", "name", "codename")

class RoleType(DjangoObjectType):
    permissions = graphene.List(PermissionType)

    class Meta:
        model = Group
        fields = ("id", "name")

    def resolve_permissions(self, info):
        return self.permissions.all()
