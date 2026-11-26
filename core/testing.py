"""Shared helpers for tests: execute GraphQL as a given user."""
from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from SolidWasteManagementSystem.schema import schema


def gql(query, user=None, **variables):
    request = RequestFactory().post('/graphql/')
    request.user = user or AnonymousUser()
    result = schema.execute(query, variable_values=variables, context_value=request)
    return SimpleNamespace(data=result.data, errors=[str(e) for e in (result.errors or [])])


def make_user(username, role='worker', area=None, **extra):
    from core.models import User
    return User.objects.create(
        username=username, email=f'{username}@example.com', user_type=role, assigned_area=area, **extra,
    )
