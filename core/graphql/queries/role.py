import graphene
from django.contrib.auth.models import Group, Permission
from core.graphql.types.role import RoleType, PermissionType
from core.graphql.auth_decorator import authenticate_graphql_api

class RoleQueries(graphene.ObjectType):
    get_all_roles = graphene.List(RoleType)
    get_role_by_id = graphene.Field(RoleType, id=graphene.Int(required=True))
    get_all_permissions = graphene.List(PermissionType)

    @staticmethod
    @authenticate_graphql_api
    def resolve_get_all_roles(root, info):
        return Group.objects.all()

    @staticmethod
    @authenticate_graphql_api
    def resolve_get_role_by_id(root, info, id):
        try:
            return Group.objects.get(id=id)
        except Group.DoesNotExist:
            return None

    @staticmethod
    @authenticate_graphql_api
    def resolve_get_all_permissions(root, info):
        return Permission.objects.all()
