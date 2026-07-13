import graphene
from .queries.user import UserQueries
from .mutations.user import CoreMutation

class Query(UserQueries, graphene.ObjectType):
    pass

class Mutation(CoreMutation, graphene.ObjectType):
    pass
