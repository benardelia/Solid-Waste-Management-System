from djoser.serializers import UserCreateSerializer as BaseUserCreateSerializer
from django.contrib.auth.models import Permission
from rest_framework import serializers


class UserCreateSerializer(BaseUserCreateSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta(BaseUserCreateSerializer.Meta):
        fields = ["id", "username", "email", "phone", "image", "user_type", "password", "first_name", "last_name", 'permissions']

    #  this methode populete the permissions fields, the should start with get_<name of field>
    #  NB: obj is the value of serialized object
    def get_permissions(self, obj):
        user_perms = set(obj.user_permissions.values_list('codename', flat=True))
        group_perms = set(Permission.objects.filter(group__user=obj).values_list('codename', flat=True))
        return list(user_perms.union(group_perms))
