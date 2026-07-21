import graphene
from django.contrib.auth.models import Group, Permission
from core.models import User
from core.graphql.types.role import RoleType
from core.graphql.types.user import UserType
from core.graphql.auth_decorator import authenticate_mutation

class CreateRole(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)

    role = graphene.Field(RoleType)
    success = graphene.Boolean()
    message = graphene.String()

    @authenticate_mutation
    def mutate(self, info, name):
        if not info.context.user.is_superuser:
            return CreateRole(success=False, message="Only superusers can create roles.")
            
        if Group.objects.filter(name=name).exists():
            return CreateRole(success=False, message="Role with this name already exists.")
            
        role = Group.objects.create(name=name)
        return CreateRole(role=role, success=True, message="Role created successfully.")

class UpdateRole(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        name = graphene.String(required=True)

    role = graphene.Field(RoleType)
    success = graphene.Boolean()
    message = graphene.String()

    @authenticate_mutation
    def mutate(self, info, id, name):
        if not info.context.user.is_superuser:
            return UpdateRole(success=False, message="Only superusers can update roles.")
            
        try:
            role = Group.objects.get(id=id)
            role.name = name
            role.save()
            return UpdateRole(role=role, success=True, message="Role updated successfully.")
        except Group.DoesNotExist:
            return UpdateRole(success=False, message="Role not found.")

class DeleteRole(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    @authenticate_mutation
    def mutate(self, info, id):
        if not info.context.user.is_superuser:
            return DeleteRole(success=False, message="Only superusers can delete roles.")
            
        try:
            role = Group.objects.get(id=id)
            role.delete()
            return DeleteRole(success=True, message="Role deleted successfully.")
        except Group.DoesNotExist:
            return DeleteRole(success=False, message="Role not found.")

class AssignPermissionsToRole(graphene.Mutation):
    class Arguments:
        role_id = graphene.Int(required=True)
        permission_ids = graphene.List(graphene.Int, required=True)

    role = graphene.Field(RoleType)
    success = graphene.Boolean()
    message = graphene.String()

    @authenticate_mutation
    def mutate(self, info, role_id, permission_ids):
        if not info.context.user.is_superuser:
            return AssignPermissionsToRole(success=False, message="Only superusers can assign permissions.")
            
        try:
            role = Group.objects.get(id=role_id)
            permissions = Permission.objects.filter(id__in=permission_ids)
            role.permissions.set(permissions)
            return AssignPermissionsToRole(role=role, success=True, message="Permissions assigned successfully.")
        except Group.DoesNotExist:
            return AssignPermissionsToRole(success=False, message="Role not found.")

class AssignRolesToUser(graphene.Mutation):
    class Arguments:
        user_id = graphene.Int(required=True)
        role_ids = graphene.List(graphene.Int, required=True)

    user = graphene.Field(UserType)
    success = graphene.Boolean()
    message = graphene.String()

    @authenticate_mutation
    def mutate(self, info, user_id, role_ids):
        if not info.context.user.is_superuser:
            return AssignRolesToUser(success=False, message="Only superusers can assign roles to users.")
            
        try:
            user = User.objects.get(id=user_id)
            roles = Group.objects.filter(id__in=role_ids)
            user.groups.set(roles)
            return AssignRolesToUser(user=user, success=True, message="Roles assigned to user successfully.")
        except User.DoesNotExist:
            return AssignRolesToUser(success=False, message="User not found.")

class RemoveRoleFromUser(graphene.Mutation):
    class Arguments:
        user_id = graphene.Int(required=True)
        role_id = graphene.Int(required=True)

    user = graphene.Field(UserType)
    success = graphene.Boolean()
    message = graphene.String()

    @authenticate_mutation
    def mutate(self, info, user_id, role_id):
        if not info.context.user.is_superuser:
            return RemoveRoleFromUser(success=False, message="Only superusers can remove roles from users.")
            
        try:
            user = User.objects.get(id=user_id)
            role = Group.objects.get(id=role_id)
            user.groups.remove(role)
            return RemoveRoleFromUser(user=user, success=True, message="Role removed from user successfully.")
        except (User.DoesNotExist, Group.DoesNotExist):
            return RemoveRoleFromUser(success=False, message="User or Role not found.")

class RoleMutation(graphene.ObjectType):
    create_role = CreateRole.Field()
    update_role = UpdateRole.Field()
    delete_role = DeleteRole.Field()
    assign_permissions_to_role = AssignPermissionsToRole.Field()
    assign_roles_to_user = AssignRolesToUser.Field()
    remove_role_from_user = RemoveRoleFromUser.Field()
