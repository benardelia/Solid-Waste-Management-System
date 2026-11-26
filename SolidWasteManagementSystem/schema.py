import graphene
import core.graphql.schema
import wastemanager.graphql.schema
from complaints.graphql.schema import ComplaintMutations, ComplaintQueries
from reference.graphql import ReferenceMutations, ReferenceQueries
from reports.graphql import ReportQueries


class Query(core.graphql.schema.Query, wastemanager.graphql.schema.Query,
            ReferenceQueries, ComplaintQueries, ReportQueries, graphene.ObjectType):
    pass


class Mutation(core.graphql.schema.Mutation, wastemanager.graphql.schema.Mutation,
               ReferenceMutations, ComplaintMutations, graphene.ObjectType):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
