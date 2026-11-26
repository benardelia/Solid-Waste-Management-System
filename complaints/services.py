"""
Complaint business rules. GraphQL resolvers and REST views call into this
module; they never change complaint state directly.
"""
from django.db import transaction
from django.db.models import Q
from graphql import GraphQLError

from core.roles import COMPLAINT_MANAGER_ROLES, has_role

from .models import Complaint, ComplaintCategory, ComplaintUpdate

ALLOWED_TRANSITIONS = {
    Complaint.STATUS_OPEN: {Complaint.STATUS_IN_PROGRESS, Complaint.STATUS_RESOLVED, Complaint.STATUS_REJECTED},
    Complaint.STATUS_IN_PROGRESS: {Complaint.STATUS_OPEN, Complaint.STATUS_RESOLVED, Complaint.STATUS_REJECTED},
    Complaint.STATUS_RESOLVED: {Complaint.STATUS_CLOSED, Complaint.STATUS_IN_PROGRESS},
    Complaint.STATUS_REJECTED: {Complaint.STATUS_OPEN},
    Complaint.STATUS_CLOSED: {Complaint.STATUS_IN_PROGRESS},
}
# Field workers may only move complaints assigned to them along this path.
WORKER_TRANSITIONS = {
    Complaint.STATUS_OPEN: {Complaint.STATUS_IN_PROGRESS, Complaint.STATUS_RESOLVED},
    Complaint.STATUS_IN_PROGRESS: {Complaint.STATUS_RESOLVED},
}


def is_manager(user):
    return has_role(user, COMPLAINT_MANAGER_ROLES)


def visible_complaints(user):
    qs = Complaint.objects.select_related('category', 'area', 'registration', 'reported_by', 'assigned_to')
    if is_manager(user):
        return qs
    scope = Q(reported_by=user) | Q(assigned_to=user)
    if user.assigned_area_id:
        scope |= Q(area_id=user.assigned_area_id)
    return qs.filter(scope)


def get_visible(user, complaint_id):
    complaint = visible_complaints(user).filter(id=complaint_id).first()
    if complaint is None:
        raise GraphQLError('Complaint not found')
    return complaint


@transaction.atomic
def create_complaint(user, *, category_id, title, description, priority=None, source='mobile', **fields):
    category = ComplaintCategory.objects.filter(id=category_id, is_active=True).first()
    if category is None:
        raise GraphQLError('Unknown complaint category')

    registration_id = fields.get('registration_id')
    if registration_id and not fields.get('area_id'):
        from wastemanager.models import Registration
        fields['area_id'] = Registration.objects.filter(id=registration_id).values_list('area_id', flat=True).first()
    if not fields.get('area_id') and user.assigned_area_id:
        fields['area_id'] = user.assigned_area_id

    allowed = {
        'area_id', 'registration_id', 'complainant_name', 'complainant_phone',
        'location_description', 'latitude', 'longitude',
    }
    complaint = Complaint.objects.create(
        category=category,
        title=title.strip(),
        description=description.strip(),
        priority=priority or category.default_priority,
        source=source,
        reported_by=user,
        **{k: v for k, v in fields.items() if k in allowed and v not in (None, '')},
    )
    ComplaintUpdate.objects.create(
        complaint=complaint, author=user, new_status=complaint.status, message='Complaint logged',
    )
    return complaint


@transaction.atomic
def change_status(user, complaint, new_status, message='', resolution_notes=None):
    if new_status not in dict(Complaint.STATUS_CHOICES):
        raise GraphQLError(f'Invalid status "{new_status}"')
    if new_status == complaint.status:
        return complaint

    if is_manager(user):
        allowed = ALLOWED_TRANSITIONS.get(complaint.status, set())
    elif complaint.assigned_to_id == user.id:
        allowed = WORKER_TRANSITIONS.get(complaint.status, set())
    else:
        raise GraphQLError('Only the assigned worker or a supervisor can change this complaint')

    if new_status not in allowed:
        raise GraphQLError(f'Cannot move a complaint from "{complaint.status}" to "{new_status}"')
    if new_status in (Complaint.STATUS_RESOLVED, Complaint.STATUS_REJECTED) and not (resolution_notes or message):
        raise GraphQLError('Please describe how the complaint was resolved or why it was rejected')

    old = complaint.status
    complaint.status = new_status
    if resolution_notes is not None:
        complaint.resolution_notes = resolution_notes
    elif new_status in (Complaint.STATUS_RESOLVED, Complaint.STATUS_REJECTED):
        complaint.resolution_notes = message
    complaint.save()
    ComplaintUpdate.objects.create(
        complaint=complaint, author=user, old_status=old, new_status=new_status, message=message,
    )
    return complaint


@transaction.atomic
def assign(user, complaint, assignee):
    if not is_manager(user):
        raise GraphQLError('You do not have permission to assign complaints')
    complaint.assigned_to = assignee
    note = f'Assigned to {assignee.get_full_name() or assignee.username}' if assignee else 'Unassigned'
    old = complaint.status
    if assignee and complaint.status == Complaint.STATUS_OPEN:
        complaint.status = Complaint.STATUS_IN_PROGRESS
    complaint.save()
    ComplaintUpdate.objects.create(
        complaint=complaint, author=user, message=note,
        old_status=old if old != complaint.status else '',
        new_status=complaint.status if old != complaint.status else '',
        is_internal=True,
    )
    return complaint


def add_comment(user, complaint, message, is_internal=False):
    if not message.strip():
        raise GraphQLError('Comment cannot be empty')
    return ComplaintUpdate.objects.create(
        complaint=complaint, author=user, message=message.strip(),
        is_internal=is_internal and is_manager(user),
    )


def update_details(user, complaint, **fields):
    if not is_manager(user):
        raise GraphQLError('You do not have permission to edit complaints')
    editable = {'title', 'description', 'priority', 'category_id', 'area_id', 'due_at'}
    for key, value in fields.items():
        if key in editable and value is not None:
            setattr(complaint, key, value)
    if fields.get('priority') and fields['priority'] not in dict(Complaint.PRIORITY_CHOICES):
        raise GraphQLError('Invalid priority')
    complaint.save()
    return complaint
