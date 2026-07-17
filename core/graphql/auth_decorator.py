from functools import wraps
from typing import Any, Callable, TypeVar
from django.contrib.auth.models import AnonymousUser
from graphene_django.views import GraphQLView
from graphql import GraphQLError
from django.http import HttpRequest
from core.firebase_auth import verify_firebase_token

F = TypeVar('F', bound=Callable[..., Any])

class JWTGraphQLView(GraphQLView):
    def parse_body(self, request: HttpRequest) -> dict[str, Any]:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            user = verify_firebase_token(token)
            if user:
                request.user = user
            else:
                request.user = AnonymousUser()
        else:
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
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        info = None
        for arg in args:
            if hasattr(arg, 'context'):
                info = arg
                break
                
        if not info:
            raise GraphQLError("Authentication required: GraphQL info object missing")
            
        user = info.context.user
        if not user or not user.is_authenticated:
            raise GraphQLError("Authentication required")
            
        return func(*args, **kwargs)
    return wrapper
