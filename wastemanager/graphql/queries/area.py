import graphene
from wastemanager.models import ProjectArea, Registration, CollectionRecord
from wastemanager.graphql.types.area import ProjectAreaType, RegistrationType, CollectionRecordType
from core.graphql.pagination import PaginationInput, paginated_field
from core.graphql.auth_decorator import authenticate_graphql_api
from django.utils import timezone
from django.db.models import Sum, DecimalField, F
from django.db.models.functions import Coalesce


class AreaMonthlyStatsType(graphene.ObjectType):
    area_id          = graphene.Int()
    area_name        = graphene.String()
    expected_amount  = graphene.Float()
    collected_amount = graphene.Float()


PaginatedRegistrationType = type('PaginatedRegistrationType', (graphene.ObjectType,), {
    'items':      graphene.List(RegistrationType),
    'pagination': graphene.Field('core.graphql.pagination.PaginationInfo'),
})

PaginatedCollectionType = type('PaginatedCollectionType', (graphene.ObjectType,), {
    'items':      graphene.List(CollectionRecordType),
    'pagination': graphene.Field('core.graphql.pagination.PaginationInfo'),
})


class WastemanagerQueries(graphene.ObjectType):
    get_all_areas         = graphene.List(ProjectAreaType)
    get_area_by_id        = graphene.Field(ProjectAreaType, id=graphene.Int(required=True))
    get_all_registrations = graphene.Field(
        PaginatedRegistrationType,
        pagination=PaginationInput(),
        area_id=graphene.Int(),
        entity_type=graphene.String(description="Filter by type: household, shop, restaurant, etc."),
    )
    get_all_collections   = graphene.Field(
        PaginatedCollectionType,
        pagination=PaginationInput(),
        area_id=graphene.Int(),
        status=graphene.String(),
        worker_id=graphene.String(),
    )
    get_area_monthly_stats = graphene.List(AreaMonthlyStatsType, area_id=graphene.Int())

    @staticmethod
    @authenticate_graphql_api
    def resolve_get_all_areas(root, info):
        return ProjectArea.objects.all()

    @staticmethod
    @authenticate_graphql_api
    def resolve_get_area_by_id(root, info, id):
        try:
            return ProjectArea.objects.get(id=id)
        except ProjectArea.DoesNotExist:
            return None

    @staticmethod
    @authenticate_graphql_api
    @paginated_field(RegistrationType)
    def resolve_get_all_registrations(root, info, area_id=None, entity_type=None):
        qs = Registration.objects.all()
        if area_id:
            qs = qs.filter(area_id=area_id)
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
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
        now            = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        areas = ProjectArea.objects.all()
        if area_id:
            areas = areas.filter(id=area_id)

        stats_list = []
        for area in areas:
            reg_qs   = Registration.objects.filter(area=area)
            expected = float(sum(
                (r.monthly_fee_override if r.monthly_fee_override is not None else area.monthly_fee)
                * r.number_of_units
                for r in reg_qs
            ))

            coll_qs   = CollectionRecord.objects.filter(
                area=area,
                timestamp__gte=start_of_month,
                status__icontains='collected',
            )
            collected = float(
                coll_qs.aggregate(
                    total=Coalesce(Sum('amount_collected'), 0.0, output_field=DecimalField())
                )['total']
            )

            stats_list.append(AreaMonthlyStatsType(
                area_id=area.id,
                area_name=area.name,
                expected_amount=expected,
                collected_amount=collected,
            ))

        return stats_list
