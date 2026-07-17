import graphene
from wastemanager.models import ProjectArea, Household, Institute, CollectionRecord
from wastemanager.graphql.types.area import ProjectAreaType, HouseholdType, InstituteType, CollectionRecordType
from core.graphql.pagination import PaginationInput, paginated_field
from core.graphql.auth_decorator import authenticate_graphql_api
from django.utils import timezone
from django.db.models import Sum, DecimalField
from django.db.models.functions import Coalesce

class AreaMonthlyStatsType(graphene.ObjectType):
    area_id = graphene.Int()
    area_name = graphene.String()
    expected_amount = graphene.Float()
    collected_amount = graphene.Float()

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
    get_all_collections = graphene.Field(PaginatedCollectionType, pagination=PaginationInput(), area_id=graphene.Int(), status=graphene.String(), worker_id=graphene.String())
    get_area_monthly_stats = graphene.List(AreaMonthlyStatsType, area_id=graphene.Int())

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
    def resolve_get_all_collections(root, info, area_id=None, status=None, worker_id=None):
        qs = CollectionRecord.objects.all().order_by('-timestamp')
        if area_id:
            qs = qs.filter(area_id=area_id)
        if status:
            qs = qs.filter(status=status)
        if worker_id:
            qs = qs.filter(worker__firebase_uid=worker_id)
        return qs

    @staticmethod
    @authenticate_graphql_api
    def resolve_get_area_monthly_stats(root, info, area_id=None):
        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        areas = ProjectArea.objects.all()
        if area_id:
            areas = areas.filter(id=area_id)

        stats_list = []
        for area in areas:
            # Expected from households
            hh_qs = Household.objects.filter(area=area)
            hh_expected = sum(h.monthly_fee_override if h.monthly_fee_override is not None else area.monthly_fee for h in hh_qs)

            # Expected from institutes
            inst_qs = Institute.objects.filter(area=area)
            inst_expected = sum(i.monthly_fee_override if i.monthly_fee_override is not None else area.monthly_fee for i in inst_qs)

            expected = float(hh_expected + inst_expected)

            # Collected
            coll_qs = CollectionRecord.objects.filter(
                area=area, 
                timestamp__gte=start_of_month,
                status__icontains='collected'
            )
            collected = float(coll_qs.aggregate(total=Coalesce(Sum('amount_collected'), 0.0, output_field=DecimalField()))['total'])

            stats_list.append(
                AreaMonthlyStatsType(
                    area_id=area.id,
                    area_name=area.name,
                    expected_amount=expected,
                    collected_amount=collected
                )
            )

        return stats_list
