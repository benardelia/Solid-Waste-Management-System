from functools import wraps

from graphql import GraphQLError
from rest_framework.permissions import BasePermission

from core.roles import has_role


def _find_info(args):
    for arg in args:
        if hasattr(arg, 'context'):
            return arg
    return None


def require_roles(*roles):
    """
    Decorator for GraphQL resolvers and mutate() methods.

    Works for both `resolve_x(root, info, **kw)` and `mutate(self, info, **kw)`
    because it locates the `info` object among the positional arguments.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            info = _find_info(args)
            user = getattr(getattr(info, 'context', None), 'user', None)
            if not user or not user.is_authenticated:
                raise GraphQLError('Authentication required')
            if roles and not has_role(user, roles):
                raise GraphQLError('You do not have permission to perform this action')
            return func(*args, **kwargs)
        return wrapper
    return decorator


class HasRole(BasePermission):
    """DRF permission: set `allowed_roles` on the view."""

    message = 'You do not have permission to perform this action'

    def has_permission(self, request, view):
        roles = getattr(view, 'allowed_roles', ())
        user = request.user
        return bool(user and user.is_authenticated and (not roles or has_role(user, roles)))
