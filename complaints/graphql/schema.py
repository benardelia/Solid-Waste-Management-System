import graphene
from django.db.models import Count, Q
from django.utils import timezone
from graphene_django import DjangoObjectType
from graphql import GraphQLError

from core.graphql.pagination import PaginationInput, paginated_field
from core.models import User
from core.permissions import require_roles
from core.roles import COMPLAINT_MANAGER_ROLES, REFERENCE_MANAGER_ROLES
from reference.graphql import LookupInput, save_lookup

from complaints import services
from complaints.models import Complaint, ComplaintCategory, ComplaintUpdate


class ComplaintCategoryType(DjangoObjectType):
    class Meta:
        model = ComplaintCategory
        fields = ('id', 'code', 'name', 'description', 'default_priority', 'sla_hours', 'sort_order', 'is_active')


class ComplaintUpdateType(DjangoObjectType):
    class Meta:
        model = ComplaintUpdate
        fields = ('id', 'author', 'message', 'old_status', 'new_status', 'is_internal', 'created_at')


class ComplaintType(DjangoObjectType):
    is_overdue = graphene.Boolean()
    photo_url = graphene.String()
    updates = graphene.List(graphene.NonNull(ComplaintUpdateType))

    class Meta:
        model = Complaint
        fields = (
            'id', 'uid', 'reference', 'category', 'title', 'description', 'status', 'priority', 'source',
            'area', 'registration', 'complainant_name', 'complainant_phone', 'location_description',
            'latitude', 'longitude', 'reported_by', 'assigned_to', 'due_at', 'resolved_at',
            'resolution_notes', 'created_at', 'updated_at',
        )
        convert_choices_to_enum = False

    def resolve_is_overdue(self, info):
        return self.is_overdue

    def resolve_photo_url(self, info):
        return info.context.build_absolute_uri(self.photo.url) if self.photo else None

    def resolve_updates(self, info):
        qs = self.updates.select_related('author')
        if not services.is_manager(info.context.user):
            qs = qs.filter(is_internal=False)
        return qs


PaginatedComplaintType = type('PaginatedComplaintType', (graphene.ObjectType,), {
    'items': graphene.List(ComplaintType),
    'pagination': graphene.Field('core.graphql.pagination.PaginationInfo'),
})


class CountByKeyType(graphene.ObjectType):
    key = graphene.String()
    label = graphene.String()
    count = graphene.Int()


class ComplaintStatsType(graphene.ObjectType):
    total = graphene.Int()
    open = graphene.Int()
    overdue = graphene.Int()
    resolved_this_month = graphene.Int()
    by_status = graphene.List(CountByKeyType)
    by_category = graphene.List(CountByKeyType)


class ComplaintQueries(graphene.ObjectType):
    complaints = graphene.Field(
        PaginatedComplaintType,
        pagination=PaginationInput(),
        status=graphene.String(),
        priority=graphene.String(),
        category_id=graphene.Int(),
        area_id=graphene.Int(),
        assigned_to_id=graphene.Int(),
        mine=graphene.Boolean(description='Only complaints assigned to or reported by me'),
        overdue=graphene.Boolean(),
        search=graphene.String(),
    )
    complaint = graphene.Field(ComplaintType, id=graphene.Int(required=True))
    complaint_stats = graphene.Field(ComplaintStatsType, area_id=graphene.Int())

    @staticmethod
    @require_roles()
    @paginated_field(ComplaintType)
    def resolve_complaints(root, info, status=None, priority=None, category_id=None, area_id=None,
                           assigned_to_id=None, mine=False, overdue=False, search=None):
        user = info.context.user
        qs = services.visible_complaints(user)
        if status:
            qs = qs.filter(status__in=status.split(','))
        if priority:
            qs = qs.filter(priority=priority)
        if category_id:
            qs = qs.filter(category_id=category_id)
        if area_id:
            qs = qs.filter(area_id=area_id)
        if assigned_to_id:
            qs = qs.filter(assigned_to_id=assigned_to_id)
        if mine:
            qs = qs.filter(Q(assigned_to=user) | Q(reported_by=user))
        if overdue:
            qs = qs.filter(status__in=Complaint.ACTIVE_STATUSES, due_at__lt=timezone.now())
        if search:
            qs = qs.filter(
                Q(reference__icontains=search) | Q(title__icontains=search)
                | Q(complainant_name__icontains=search) | Q(complainant_phone__icontains=search)
            )
        return qs

    @staticmethod
    @require_roles()
    def resolve_complaint(root, info, id):
        return services.get_visible(info.context.user, id)

    @staticmethod
    @require_roles()
    def resolve_complaint_stats(root, info, area_id=None):
        qs = services.visible_complaints(info.context.user)
        if area_id:
            qs = qs.filter(area_id=area_id)
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        statuses = dict(Complaint.STATUS_CHOICES)
        by_status = {r['status']: r['n'] for r in qs.values('status').annotate(n=Count('id'))}
        by_category = qs.values('category__code', 'category__name').annotate(n=Count('id')).order_by('-n')
        return ComplaintStatsType(
            total=qs.count(),
            open=qs.filter(status__in=Complaint.ACTIVE_STATUSES).count(),
            overdue=qs.filter(status__in=Complaint.ACTIVE_STATUSES, due_at__lt=now).count(),
            resolved_this_month=qs.filter(resolved_at__gte=month_start, status=Complaint.STATUS_RESOLVED).count(),
            by_status=[CountByKeyType(key=k, label=str(v), count=by_status.get(k, 0)) for k, v in statuses.items()],
            by_category=[
                CountByKeyType(key=r['category__code'], label=r['category__name'], count=r['n'])
                for r in by_category
            ],
        )


class CreateComplaint(graphene.Mutation):
    class Arguments:
        category_id = graphene.Int(required=True)
        title = graphene.String(required=True)
        description = graphene.String(required=True)
        priority = graphene.String()
        source = graphene.String(default_value='mobile')
        area_id = graphene.Int()
        registration_id = graphene.Int()
        complainant_name = graphene.String()
        complainant_phone = graphene.String()
        location_description = graphene.String()
        latitude = graphene.Float()
        longitude = graphene.Float()

    complaint = graphene.Field(ComplaintType)
    success = graphene.Boolean()

    @require_roles()
    def mutate(self, info, **kwargs):
        if kwargs.get('priority') and kwargs['priority'] not in dict(Complaint.PRIORITY_CHOICES):
            raise GraphQLError('Invalid priority')
        if kwargs.get('source') not in dict(Complaint.SOURCE_CHOICES):
            kwargs['source'] = 'other'
        complaint = services.create_complaint(info.context.user, **kwargs)
        return CreateComplaint(complaint=complaint, success=True)


class UpdateComplaintStatus(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        status = graphene.String(required=True)
        message = graphene.String(default_value='')
        resolution_notes = graphene.String()

    complaint = graphene.Field(ComplaintType)
    success = graphene.Boolean()

    @require_roles()
    def mutate(self, info, id, status, message='', resolution_notes=None):
        user = info.context.user
        complaint = services.change_status(user, services.get_visible(user, id), status, message, resolution_notes)
        return UpdateComplaintStatus(complaint=complaint, success=True)


class AssignComplaint(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        user_id = graphene.Int(description='Omit to unassign')

    complaint = graphene.Field(ComplaintType)
    success = graphene.Boolean()

    @require_roles(*COMPLAINT_MANAGER_ROLES)
    def mutate(self, info, id, user_id=None):
        user = info.context.user
        assignee = None
        if user_id:
            assignee = User.objects.filter(id=user_id, is_active=True).first()
            if assignee is None:
                raise GraphQLError('User not found')
        complaint = services.assign(user, services.get_visible(user, id), assignee)
        return AssignComplaint(complaint=complaint, success=True)


class AddComplaintComment(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        message = graphene.String(required=True)
        is_internal = graphene.Boolean(default_value=False)

    update = graphene.Field(ComplaintUpdateType)
    success = graphene.Boolean()

    @require_roles()
    def mutate(self, info, id, message, is_internal=False):
        user = info.context.user
        update = services.add_comment(user, services.get_visible(user, id), message, is_internal)
        return AddComplaintComment(update=update, success=True)


class UpdateComplaint(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        title = graphene.String()
        description = graphene.String()
        priority = graphene.String()
        category_id = graphene.Int()
        area_id = graphene.Int()
        due_at = graphene.DateTime()

    complaint = graphene.Field(ComplaintType)
    success = graphene.Boolean()

    @require_roles(*COMPLAINT_MANAGER_ROLES)
    def mutate(self, info, id, **fields):
        user = info.context.user
        complaint = services.update_details(user, services.get_visible(user, id), **fields)
        return UpdateComplaint(complaint=complaint, success=True)


class ComplaintCategoryInput(LookupInput):
    default_priority = graphene.String()
    sla_hours = graphene.Int()


class SaveComplaintCategory(graphene.Mutation):
    class Arguments:
        input = ComplaintCategoryInput(required=True)

    category = graphene.Field(ComplaintCategoryType)

    @require_roles(*REFERENCE_MANAGER_ROLES)
    def mutate(self, info, input):
        return SaveComplaintCategory(category=save_lookup(ComplaintCategory, input))


class ComplaintMutations(graphene.ObjectType):
    create_complaint = CreateComplaint.Field()
    update_complaint_status = UpdateComplaintStatus.Field()
    assign_complaint = AssignComplaint.Field()
    add_complaint_comment = AddComplaintComment.Field()
    update_complaint = UpdateComplaint.Field()
    save_complaint_category = SaveComplaintCategory.Field()
