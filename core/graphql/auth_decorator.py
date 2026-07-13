from functools import wraps
from typing import Any, Callable, TypeVar
from django.contrib.auth.models import AnonymousUser
from graphene_django.views import GraphQLView
from graphql import GraphQLError
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.http import HttpRequest

F = TypeVar('F', bound=Callable[..., Any])

class JWTGraphQLView(GraphQLView):
    def parse_body(self, request: HttpRequest) -> dict[str, Any]:
        auth = JWTAuthentication()
        try:
            user_auth_tuple = auth.authenticate(request)
            if user_auth_tuple is not None:
                request.user, _ = user_auth_tuple
            elif not (hasattr(request, 'user') and request.user.is_authenticated):
                request.user = AnonymousUser()
        except Exception:
            if not (hasattr(request, 'user') and request.user.is_authenticated):
                request.user = AnonymousUser()
        return super().parse_body(request)

def authenticate_graphql_api(func: F) -> F:
    @wraps(func)
    def wrapper(root: Any, info: Any, **kwargs: Any) -> Any:
        user = info.context.user
        if not user or not user.is_authenticated:
            raise GraphQLError("Authentication required")
        return func(root, info, **kwargs)
    return wrapper

def authenticate_mutation(func: F) -> F:
    @wraps(func)
    def wrapper(cls: Any, root: Any, info: Any, *args: Any, **kwargs: Any) -> Any:
        user = info.context.user
        if not user or not user.is_authenticated:
            raise Exception("Authentication required")
        return func(cls, root, info, *args, **kwargs)
    return wrapper
