import graphene
from core.models import User
from core.graphql.types.user import UserType
from core.graphql.pagination import PaginationInput, paginated_field
from core.graphql.auth_decorator import authenticate_graphql_api

PaginatedUserType = type('PaginatedUserType', (graphene.ObjectType,), {
    'items': graphene.List(UserType),
    'pagination': graphene.Field('core.graphql.pagination.PaginationInfo')
})

class UserQueries(graphene.ObjectType):
    get_all_users = graphene.Field(
        PaginatedUserType,
        pagination=PaginationInput(),
        user_type=graphene.String(description="Filter by role: worker, admin, manager, etc."),
    )
    get_user_by_id = graphene.Field(UserType, id=graphene.Int(required=True))

    @staticmethod
    @authenticate_graphql_api
    @paginated_field(UserType)
    def resolve_get_all_users(root, info, user_type=None):
        qs = User.objects.all().order_by('username')
        if user_type:
            qs = qs.filter(user_type=user_type)
        return qs

    @staticmethod
    @authenticate_graphql_api
    def resolve_get_user_by_id(root, info, id):
        try:
            return User.objects.get(id=id)
        except User.DoesNotExist:
            return None
