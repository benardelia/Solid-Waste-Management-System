import graphene
from wastemanager.models import ProjectArea, Household, Institute, CollectionRecord
from wastemanager.graphql.types.area import ProjectAreaType, HouseholdType, InstituteType, CollectionRecordType
from core.graphql.pagination import PaginationInput, paginated_field
from core.graphql.auth_decorator import authenticate_graphql_api

PaginatedHouseholdType = type('PaginatedHouseholdType', (graphene.ObjectType,), {
    'items': graphene.List(HouseholdType),
    'pagination': graphene.Field('core.graphql.pagination.PaginationInfo')
})

PaginatedInstituteType = type('PaginatedInstituteType', (graphene.ObjectType,), {
    'items': graphene.List(InstituteType),
    'pagination': graphene.Field('core.graphql.pagination.PaginationInfo')
})

PaginatedCollectionType = type('PaginatedCollectionType', (graphene.ObjectType,), {
    'items': graphene.List(CollectionRecordType),
    'pagination': graphene.Field('core.graphql.pagination.PaginationInfo')
})

class WastemanagerQueries(graphene.ObjectType):
    get_all_areas = graphene.List(ProjectAreaType)
    get_all_households = graphene.Field(PaginatedHouseholdType, pagination=PaginationInput(), area_id=graphene.Int())
    get_all_institutes = graphene.Field(PaginatedInstituteType, pagination=PaginationInput(), area_id=graphene.Int())
    get_all_collections = graphene.Field(PaginatedCollectionType, pagination=PaginationInput(), area_id=graphene.Int(), status=graphene.String())

    @staticmethod
    @authenticate_graphql_api
    def resolve_get_all_areas(root, info):
        return ProjectArea.objects.all()

    @staticmethod
    @authenticate_graphql_api
    @paginated_field(HouseholdType)
    def resolve_get_all_households(root, info, area_id=None):
        qs = Household.objects.all()
        if area_id:
            qs = qs.filter(area_id=area_id)
        return qs

    @staticmethod
    @authenticate_graphql_api
    @paginated_field(InstituteType)
    def resolve_get_all_institutes(root, info, area_id=None):
        qs = Institute.objects.all()
        if area_id:
            qs = qs.filter(area_id=area_id)
        return qs

    @staticmethod
    @authenticate_graphql_api
    @paginated_field(CollectionRecordType)
    def resolve_get_all_collections(root, info, area_id=None, status=None):
        qs = CollectionRecord.objects.all()
        if area_id:
            qs = qs.filter(area_id=area_id)
        if status:
            qs = qs.filter(status=status)
        return qs
