import graphene
from core.models import User
from core.graphql.types.user import UserType
from core.graphql.pagination import PaginationInput, paginated_field
from django.db.models import Q
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
        area_id=graphene.Int(),
        search=graphene.String(),
        is_active=graphene.Boolean(),
    )
    get_user_by_id = graphene.Field(UserType, id=graphene.Int(required=True))
    me = graphene.Field(UserType)

    @staticmethod
    def resolve_me(root, info):
        user = info.context.user
        return user if user and user.is_authenticated else None

    @staticmethod
    @authenticate_graphql_api
    @paginated_field(UserType)
    def resolve_get_all_users(root, info, user_type=None, area_id=None, search=None, is_active=None):
        qs = User.objects.select_related('assigned_area').order_by('first_name', 'username')
        if user_type:
            qs = qs.filter(user_type=user_type)
        if area_id:
            qs = qs.filter(assigned_area_id=area_id)
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        if search:
            qs = qs.filter(
                Q(username__icontains=search) | Q(email__icontains=search) | Q(first_name__icontains=search)
                | Q(last_name__icontains=search) | Q(phone__icontains=search)
            )
        return qs

    @staticmethod
    @authenticate_graphql_api
    def resolve_get_user_by_id(root, info, id):
        try:
            return User.objects.get(id=id)
        except User.DoesNotExist:
            return None
