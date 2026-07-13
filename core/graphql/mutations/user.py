import graphene
from core.models import User
from core.graphql.types.user import UserType

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

class CoreMutation(graphene.ObjectType):
    register_user = RegisterUser.Field()
