import graphene
from .queries.user import UserQueries
from .mutations.user import CoreMutation
from .queries.role import RoleQueries
from .mutations.role import RoleMutation

class Query(UserQueries, RoleQueries, graphene.ObjectType):
    pass

class Mutation(CoreMutation, RoleMutation, graphene.ObjectType):
    pass
