import graphene
from core.models import User
from wastemanager.models import ProjectArea
from core.graphql.types.user import UserType
from core.graphql.auth_decorator import authenticate_graphql_api

class RegisterUser(graphene.Mutation):
    class Arguments:
        username = graphene.String(required=True)
        password = graphene.String(required=True)
        email = graphene.String(required=True)
        first_name = graphene.String()
        last_name = graphene.String()
        phone = graphene.String()
        user_type = graphene.String()

    user = graphene.Field(UserType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, username, password, email, **kwargs):
        if User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
            return RegisterUser(success=False, message="Username or Email already exists")
        
        user = User(
            username=username,
            email=email,
            first_name=kwargs.get('first_name', ''),
            last_name=kwargs.get('last_name', ''),
            phone=kwargs.get('phone', ''),
            user_type=kwargs.get('user_type', 'worker')
        )
        user.set_password(password)
        user.save()
        return RegisterUser(user=user, success=True, message="User registered successfully")


class ReassignWorker(graphene.Mutation):
    """Reassign a worker (or any user) to a different project area."""
    class Arguments:
        user_id = graphene.Int(required=True, description="Django DB user ID")
        area_id = graphene.Int(required=True, description="Target ProjectArea ID")

    success = graphene.Boolean()
    message = graphene.String()
    user    = graphene.Field(UserType)

    @staticmethod
    @authenticate_graphql_api
    def mutate(root, info, user_id, area_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return ReassignWorker(success=False, message=f"User {user_id} not found")

        try:
            area = ProjectArea.objects.get(id=area_id)
        except ProjectArea.DoesNotExist:
            return ReassignWorker(success=False, message=f"Area {area_id} not found")

        user.assigned_area = area
        user.save(update_fields=['assigned_area'])
        return ReassignWorker(success=True, message="Worker reassigned successfully", user=user)


class CoreMutation(graphene.ObjectType):
    register_user   = RegisterUser.Field()
    reassign_worker = ReassignWorker.Field()
