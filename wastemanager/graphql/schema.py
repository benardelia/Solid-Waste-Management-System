import graphene
from .queries.area import WastemanagerQueries
from .mutations.area import WastemanagerMutation

class Query(WastemanagerQueries, graphene.ObjectType):
    pass

class Mutation(WastemanagerMutation, graphene.ObjectType):
    pass
