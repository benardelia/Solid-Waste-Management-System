import graphene
import core.graphql.schema
import wastemanager.graphql.schema

class Query(core.graphql.schema.Query, wastemanager.graphql.schema.Query, graphene.ObjectType):
    pass

class Mutation(core.graphql.schema.Mutation, wastemanager.graphql.schema.Mutation, graphene.ObjectType):
    pass

schema = graphene.Schema(query=Query, mutation=Mutation)
