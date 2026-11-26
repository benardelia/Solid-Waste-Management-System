import graphene
from wastemanager.models import ProjectArea, Registration, CollectionRecord
from wastemanager.graphql.types.area import ProjectAreaType, RegistrationType, CollectionRecordType
from core.graphql.pagination import PaginationInput, paginated_field
from core.graphql.auth_decorator import authenticate_graphql_api
from datetime import timedelta

from django.utils import timezone
from django.db.models import Count, Q, Sum, DecimalField, F
from django.db.models.functions import Coalesce, TruncDate
from core.permissions import require_roles
from core.roles import STAFF_ROLES


class AreaMonthlyStatsType(graphene.ObjectType):
    area_id          = graphene.Int()
    area_name        = graphene.String()
    expected_amount  = graphene.Float()
    collected_amount = graphene.Float()


class TrendPointType(graphene.ObjectType):
    date = graphene.Date()
    visits = graphene.Int()
    amount = graphene.Float()
    missed = graphene.Int()


class AreaPerformanceType(graphene.ObjectType):
    area_id = graphene.Int()
    area_name = graphene.String()
    registrations = graphene.Int()
    expected = graphene.Float()
    collected = graphene.Float()
    rate = graphene.Float()


class DashboardSummaryType(graphene.ObjectType):
    start_date = graphene.Date()
    end_date = graphene.Date()
    total_registrations = graphene.Int()
    new_registrations = graphene.Int()
    total_workers = graphene.Int()
    active_workers = graphene.Int(description='Workers who logged a collection in the period')
    visits = graphene.Int()
    missed = graphene.Int()
    expected_amount = graphene.Float(description='Monthly expected × months in period')
    collected_amount = graphene.Float()
    collection_rate = graphene.Float()
    open_complaints = graphene.Int()
    overdue_complaints = graphene.Int()
    trend = graphene.List(TrendPointType)
    areas = graphene.List(AreaPerformanceType)
    registrations_by_type = graphene.List('complaints.graphql.schema.CountByKeyType')


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
        search=graphene.String(description="Search by owner name or house number"),
    )
    get_all_collections   = graphene.Field(
        PaginatedCollectionType,
        pagination=PaginationInput(),
        area_id=graphene.Int(),
        status=graphene.String(),
        worker_id=graphene.String(description="Worker Firebase UID (mobile)"),
        worker_db_id=graphene.Int(description="Worker Django id (admin portal)"),
        registration_id=graphene.Int(description="Filter by registration"),
        start_date=graphene.Date(),
        end_date=graphene.Date(),
        search=graphene.String(description="Owner name or worker username"),
    )
    dashboard_summary = graphene.Field(
        DashboardSummaryType,
        area_id=graphene.Int(), start_date=graphene.Date(), end_date=graphene.Date(),
    )
    get_area_monthly_stats = graphene.List(AreaMonthlyStatsType, area_id=graphene.Int())

    @staticmethod
    @authenticate_graphql_api
    def resolve_get_all_areas(root, info):
        return ProjectArea.objects.annotate(
            n_registrations=Count('registrations', distinct=True),
            n_workers=Count('assigned_users', filter=Q(assigned_users__user_type='worker'), distinct=True),
        ).order_by('name')

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
    def resolve_get_all_registrations(root, info, area_id=None, entity_type=None, search=None):
        qs = Registration.objects.select_related('area').order_by('-created_at')
        if area_id:
            qs = qs.filter(area_id=area_id)
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if search:
            qs = qs.filter(
                Q(owner_name__icontains=search) | Q(house_number__icontains=search)
                | Q(owners_contact__icontains=search) | Q(ward__icontains=search)
                | Q(village__icontains=search)
            )
        return qs

    @staticmethod
    @authenticate_graphql_api
    @paginated_field(CollectionRecordType)
    def resolve_get_all_collections(root, info, area_id=None, status=None, worker_id=None, registration_id=None,
                                    worker_db_id=None, start_date=None, end_date=None, search=None):
        qs = CollectionRecord.objects.select_related('worker', 'area', 'registration').order_by('-timestamp')
        if worker_db_id:
            qs = qs.filter(worker_id=worker_db_id)
        if start_date:
            qs = qs.filter(timestamp__date__gte=start_date)
        if end_date:
            qs = qs.filter(timestamp__date__lte=end_date)
        if search:
            qs = qs.filter(Q(registration__owner_name__icontains=search) | Q(worker__username__icontains=search))
        if area_id:
            qs = qs.filter(area_id=area_id)
        if status:
            qs = qs.filter(status=status)
        if worker_id:
            qs = qs.filter(worker__firebase_uid=worker_id)
        if registration_id:
            qs = qs.filter(registration_id=registration_id)
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

    @staticmethod
    @require_roles(*STAFF_ROLES)
    def resolve_dashboard_summary(root, info, area_id=None, start_date=None, end_date=None):
        from complaints.models import Complaint
        from core.models import User
        from reference.models import EntityType
        from reports.registry import ReportFilters, revenue_by_area_report

        filters = ReportFilters.from_params({'start_date': start_date, 'end_date': end_date, 'area_id': area_id})
        revenue = revenue_by_area_report(filters)

        regs = Registration.objects.all()
        colls = CollectionRecord.objects.filter(timestamp__gte=filters.start_dt, timestamp__lt=filters.end_dt)
        workers = User.objects.filter(user_type='worker', is_active=True)
        complaints = Complaint.objects.filter(status__in=Complaint.ACTIVE_STATUSES)
        if area_id:
            regs, colls = regs.filter(area_id=area_id), colls.filter(area_id=area_id)
            workers, complaints = workers.filter(assigned_area_id=area_id), complaints.filter(area_id=area_id)

        by_day = {
            r['day']: r for r in colls.annotate(day=TruncDate('timestamp')).values('day').annotate(
                visits=Count('id'), amount=Coalesce(Sum('amount_collected'), 0, output_field=DecimalField()),
                missed=Count('id', filter=Q(status='missed')),
            )
        }
        trend, day = [], filters.start_date
        while day <= filters.end_date:
            r = by_day.get(day, {})
            trend.append(TrendPointType(date=day, visits=r.get('visits', 0), amount=float(r.get('amount') or 0),
                                        missed=r.get('missed', 0)))
            day += timedelta(days=1)

        expected = sum(float(r['expected']) for r in revenue.rows)
        collected = sum(float(r['collected']) for r in revenue.rows)
        labels = dict(EntityType.objects.values_list('code', 'name'))
        from complaints.graphql.schema import CountByKeyType
        return DashboardSummaryType(
            start_date=filters.start_date, end_date=filters.end_date,
            total_registrations=regs.count(),
            new_registrations=regs.filter(created_at__gte=filters.start_dt, created_at__lt=filters.end_dt).count(),
            total_workers=workers.count(),
            active_workers=colls.values('worker_id').distinct().count(),
            visits=colls.count(),
            missed=colls.filter(status='missed').count(),
            expected_amount=expected, collected_amount=collected,
            collection_rate=round(collected / expected * 100, 1) if expected else 0.0,
            open_complaints=complaints.count(),
            overdue_complaints=complaints.filter(due_at__lt=timezone.now()).count(),
            trend=trend,
            areas=[
                AreaPerformanceType(
                    area_id=None, area_name=r['area'], registrations=r['registrations'],
                    expected=float(r['expected']), collected=float(r['collected']), rate=r['rate'],
                ) for r in revenue.rows
            ],
            registrations_by_type=[
                CountByKeyType(key=r['entity_type'], label=labels.get(r['entity_type'], r['entity_type']), count=r['n'])
                for r in regs.values('entity_type').annotate(n=Count('id')).order_by('-n')
            ],
        )
