"""
Report definitions.

Each report is a function `(filters) -> ReportResult`. The same result feeds
the on-screen preview (GraphQL `runReport`) and every export format
(reports/exporters.py), so numbers can't differ between screen and file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Callable

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone


@dataclass
class ReportFilters:
    start_date: date
    end_date: date
    area_id: int | None = None
    worker_id: int | None = None
    status: str | None = None
    entity_type: str | None = None
    category_id: int | None = None

    @classmethod
    def from_params(cls, params) -> 'ReportFilters':
        """Build from a dict / QueryDict. Default period: current month to date."""
        today = timezone.localdate()

        def parse(name, default):
            raw = params.get(name) if params else None
            if not raw:
                return default
            if isinstance(raw, date):
                return raw
            try:
                return date.fromisoformat(str(raw)[:10])
            except ValueError:
                raise ValueError(f'Invalid {name}: use YYYY-MM-DD')

        def parse_int(name):
            raw = params.get(name) if params else None
            if raw in (None, ''):
                return None
            try:
                return int(raw)
            except (TypeError, ValueError):
                raise ValueError(f'Invalid {name}')

        start = parse('start_date', today.replace(day=1))
        end = parse('end_date', today)
        if end < start:
            raise ValueError('end_date must be on or after start_date')
        if (end - start).days > 366 * 3:
            raise ValueError('Report period cannot exceed 3 years')
        return cls(
            start_date=start, end_date=end,
            area_id=parse_int('area_id'), worker_id=parse_int('worker_id'),
            status=(params.get('status') or None) if params else None,
            entity_type=(params.get('entity_type') or None) if params else None,
            category_id=parse_int('category_id'),
        )

    @property
    def start_dt(self):
        return timezone.make_aware(datetime.combine(self.start_date, time.min))

    @property
    def end_dt(self):
        """Exclusive upper bound: midnight after end_date."""
        return timezone.make_aware(datetime.combine(self.end_date + timedelta(days=1), time.min))

    @property
    def months(self) -> int:
        """Billing months touched by the period (a fee is charged per month)."""
        return (self.end_date.year - self.start_date.year) * 12 + self.end_date.month - self.start_date.month + 1

    def describe(self, area_name=None) -> str:
        period = f"{self.start_date:%d %b %Y} – {self.end_date:%d %b %Y}"
        return f"{period} · {area_name}" if area_name else f"{period} · All areas"


@dataclass
class Column:
    key: str
    label: str
    kind: str = 'text'  # text | number | money | percent | date | datetime


@dataclass
class ReportResult:
    title: str
    subtitle: str
    columns: list[Column]
    rows: list[dict]
    summary: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class ReportDefinition:
    key: str
    title: str
    description: str
    filters: tuple[str, ...]
    build: Callable[[ReportFilters], ReportResult]


REPORTS: dict[str, ReportDefinition] = {}


def report(key, title, description, filters=('area_id',)):
    def decorator(fn):
        REPORTS[key] = ReportDefinition(key, title, description, ('start_date', 'end_date', *filters), fn)
        return fn
    return decorator


def run_report(key: str, filters: ReportFilters) -> ReportResult:
    definition = REPORTS.get(key)
    if definition is None:
        raise KeyError(key)
    return definition.build(filters)


# ------------------------------------------------------------------ helpers

def money(value) -> str:
    return f"TZS {Decimal(value or 0):,.0f}"


def pct(part, whole) -> float:
    return round(float(part) / float(whole) * 100, 1) if whole else 0.0


def _area_name(filters):
    if not filters.area_id:
        return None
    from wastemanager.models import ProjectArea
    return ProjectArea.objects.filter(id=filters.area_id).values_list('name', flat=True).first()


def _collections(filters):
    from wastemanager.models import CollectionRecord
    qs = CollectionRecord.objects.filter(timestamp__gte=filters.start_dt, timestamp__lt=filters.end_dt)
    if filters.area_id:
        qs = qs.filter(area_id=filters.area_id)
    if filters.worker_id:
        qs = qs.filter(worker_id=filters.worker_id)
    if filters.status:
        qs = qs.filter(status=filters.status)
    if filters.entity_type:
        qs = qs.filter(registration__entity_type=filters.entity_type)
    return qs


def _registrations(filters):
    from wastemanager.models import Registration
    qs = Registration.objects.select_related('area')
    if filters.area_id:
        qs = qs.filter(area_id=filters.area_id)
    if filters.entity_type:
        qs = qs.filter(entity_type=filters.entity_type)
    return qs


def _monthly_fee_expr():
    """Per-registration monthly charge: (override or area fee) × units."""
    return ExpressionWrapper(
        Coalesce('monthly_fee_override', 'area__monthly_fee') * F('number_of_units'),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )


def _entity_labels():
    from reference.models import EntityType
    return dict(EntityType.objects.values_list('code', 'name'))


def _person(user):
    if user is None:
        return ''
    return user.get_full_name() or user.username


ZERO = Value(Decimal('0'), output_field=DecimalField(max_digits=14, decimal_places=2))


# ------------------------------------------------------------------ reports

@report('collections', 'Collection log',
        'Every collection visit in the period with worker, status and amount.',
        filters=('area_id', 'worker_id', 'status', 'entity_type'))
def collections_report(filters: ReportFilters) -> ReportResult:
    from wastemanager.models import CollectionRecord
    labels = _entity_labels()
    statuses = dict(CollectionRecord.STATUS_CHOICES)
    qs = _collections(filters).select_related('worker', 'area', 'registration').order_by('-timestamp')
    rows = [{
        'timestamp': timezone.localtime(c.timestamp),
        'area': c.area.name,
        'entity_type': labels.get(c.registration.entity_type, c.registration.entity_type) if c.registration else '',
        'owner': c.registration.owner_name if c.registration else 'Unknown',
        'house_number': c.registration.house_number if c.registration else '',
        'worker': _person(c.worker),
        'status': statuses.get(c.status, c.status),
        'amount': c.amount_collected,
    } for c in qs]

    agg = qs.aggregate(total=Coalesce(Sum('amount_collected'), ZERO), n=Count('id'))
    by_status = dict(qs.values_list('status').annotate(n=Count('id')))
    summary = [('Visits', f"{agg['n']:,}"), ('Amount collected', money(agg['total']))]
    summary += [(statuses.get(s, s), f"{n:,}") for s, n in sorted(by_status.items())]
    return ReportResult(
        title='Collection log',
        subtitle=filters.describe(_area_name(filters)),
        columns=[
            Column('timestamp', 'Date & time', 'datetime'), Column('area', 'Area'),
            Column('entity_type', 'Type'), Column('owner', 'Owner'), Column('house_number', 'House no.'),
            Column('worker', 'Worker'), Column('status', 'Status'), Column('amount', 'Amount (TZS)', 'money'),
        ],
        rows=rows, summary=summary,
    )


@report('revenue_by_area', 'Revenue by area',
        'Expected fees versus amounts collected for each project area.', filters=('area_id', 'entity_type'))
def revenue_by_area_report(filters: ReportFilters) -> ReportResult:
    from wastemanager.models import ProjectArea
    areas = ProjectArea.objects.order_by('name')
    if filters.area_id:
        areas = areas.filter(id=filters.area_id)

    reg_stats = {
        r['area_id']: r for r in _registrations(filters).values('area_id').annotate(
            n=Count('id'), units=Coalesce(Sum('number_of_units'), 0),
            monthly=Coalesce(Sum(_monthly_fee_expr()), ZERO),
        )
    }
    coll_stats = {
        r['area_id']: r for r in _collections(filters).values('area_id').annotate(
            total=Coalesce(Sum('amount_collected'), ZERO), visits=Count('id'),
            missed=Count('id', filter=Q(status='missed')),
        )
    }

    rows, tot_exp, tot_col = [], Decimal(0), Decimal(0)
    for area in areas:
        reg = reg_stats.get(area.id, {})
        col = coll_stats.get(area.id, {})
        expected = (reg.get('monthly') or Decimal(0)) * filters.months
        collected = col.get('total') or Decimal(0)
        tot_exp += expected
        tot_col += collected
        rows.append({
            'area': area.name,
            'monthly_fee': area.monthly_fee,
            'registrations': reg.get('n', 0),
            'units': reg.get('units', 0),
            'visits': col.get('visits', 0),
            'missed': col.get('missed', 0),
            'expected': expected,
            'collected': collected,
            'outstanding': max(expected - collected, Decimal(0)),
            'rate': pct(collected, expected),
        })
    return ReportResult(
        title='Revenue by area',
        subtitle=f"{filters.describe(_area_name(filters))} · {filters.months} billing month(s)",
        columns=[
            Column('area', 'Area'), Column('monthly_fee', 'Base fee', 'money'),
            Column('registrations', 'Registrations', 'number'), Column('units', 'Units', 'number'),
            Column('visits', 'Visits', 'number'), Column('missed', 'Missed', 'number'),
            Column('expected', 'Expected (TZS)', 'money'), Column('collected', 'Collected (TZS)', 'money'),
            Column('outstanding', 'Outstanding (TZS)', 'money'), Column('rate', 'Collection rate', 'percent'),
        ],
        rows=rows,
        summary=[
            ('Expected', money(tot_exp)), ('Collected', money(tot_col)),
            ('Outstanding', money(max(tot_exp - tot_col, Decimal(0)))),
            ('Collection rate', f"{pct(tot_col, tot_exp)}%"),
        ],
    )


@report('worker_performance', 'Worker performance',
        'Visits, missed pickups and money collected per worker.', filters=('area_id', 'worker_id'))
def worker_performance_report(filters: ReportFilters) -> ReportResult:
    from core.models import User
    stats = _collections(filters).values('worker_id').annotate(
        visits=Count('id'),
        collected=Count('id', filter=Q(status__icontains='collected')),
        missed=Count('id', filter=Q(status='missed')),
        unpaid=Count('id', filter=Q(status='unpaid')),
        amount=Coalesce(Sum('amount_collected'), ZERO),
        last=Max('timestamp'),
        households=Count('registration', distinct=True),
    )
    users = User.objects.select_related('assigned_area').in_bulk([s['worker_id'] for s in stats])
    rows = []
    for s in sorted(stats, key=lambda s: s['amount'], reverse=True):
        u = users.get(s['worker_id'])
        rows.append({
            'worker': _person(u), 'phone': (u.phone if u else '') or '',
            'area': u.assigned_area.name if u and u.assigned_area else '',
            'visits': s['visits'], 'households': s['households'], 'collected': s['collected'],
            'missed': s['missed'], 'unpaid': s['unpaid'], 'amount': s['amount'],
            'success_rate': pct(s['collected'], s['visits']),
            'last_activity': timezone.localtime(s['last']) if s['last'] else None,
        })
    total = sum((r['amount'] for r in rows), Decimal(0))
    return ReportResult(
        title='Worker performance',
        subtitle=filters.describe(_area_name(filters)),
        columns=[
            Column('worker', 'Worker'), Column('phone', 'Phone'), Column('area', 'Assigned area'),
            Column('visits', 'Visits', 'number'), Column('households', 'Premises', 'number'),
            Column('collected', 'Collected', 'number'), Column('missed', 'Missed', 'number'),
            Column('unpaid', 'Unpaid', 'number'), Column('amount', 'Amount (TZS)', 'money'),
            Column('success_rate', 'Success rate', 'percent'), Column('last_activity', 'Last activity', 'datetime'),
        ],
        rows=rows,
        summary=[('Active workers', str(len(rows))), ('Amount collected', money(total))],
    )


@report('registrations', 'Registered premises',
        'All registered households and businesses with their fees and last collection.',
        filters=('area_id', 'entity_type'))
def registrations_report(filters: ReportFilters) -> ReportResult:
    labels = _entity_labels()
    qs = _registrations(filters).annotate(monthly_charge=_monthly_fee_expr()).order_by('area__name', 'owner_name')
    new_in_period = qs.filter(created_at__gte=filters.start_dt, created_at__lt=filters.end_dt).count()
    rows = [{
        'entity_type': labels.get(r.entity_type, r.entity_type), 'owner': r.owner_name,
        'contact': r.owners_contact or '', 'area': r.area.name, 'district': r.district, 'ward': r.ward,
        'village': r.village, 'house_number': r.house_number, 'postcode': r.postcode or '',
        'units': r.number_of_units, 'waste_bin': r.waste_bin_present, 'monthly_charge': r.monthly_charge,
        'last_status': r.last_collection_status or '',
        'last_collection': timezone.localtime(r.last_collection_date) if r.last_collection_date else None,
        'registered_on': timezone.localtime(r.created_at).date(),
    } for r in qs]
    by_type = {}
    for r in rows:
        by_type[r['entity_type']] = by_type.get(r['entity_type'], 0) + 1
    return ReportResult(
        title='Registered premises',
        subtitle=f"As of {filters.end_date:%d %b %Y} · {_area_name(filters) or 'All areas'}",
        columns=[
            Column('entity_type', 'Type'), Column('owner', 'Owner'), Column('contact', 'Contact'),
            Column('area', 'Area'), Column('district', 'District'), Column('ward', 'Ward'),
            Column('village', 'Village / Mtaa'), Column('house_number', 'House no.'), Column('postcode', 'Postcode'),
            Column('units', 'Units', 'number'), Column('waste_bin', 'Bin'),
            Column('monthly_charge', 'Monthly charge', 'money'), Column('last_status', 'Last status'),
            Column('last_collection', 'Last collection', 'datetime'), Column('registered_on', 'Registered', 'date'),
        ],
        rows=rows,
        summary=[('Total premises', f"{len(rows):,}"), ('Registered in period', f"{new_in_period:,}")]
        + [(k, f"{v:,}") for k, v in sorted(by_type.items())],
    )


@report('defaulters', 'Outstanding balances',
        'Premises that paid less than their expected fee during the period.', filters=('area_id', 'entity_type'))
def defaulters_report(filters: ReportFilters) -> ReportResult:
    labels = _entity_labels()
    paid = dict(
        _collections(ReportFilters(filters.start_date, filters.end_date, area_id=filters.area_id))
        .filter(registration__isnull=False)
        .values_list('registration_id').annotate(total=Sum('amount_collected'))
    )
    rows, total_balance = [], Decimal(0)
    qs = _registrations(filters).annotate(monthly_charge=_monthly_fee_expr()).order_by('area__name', 'owner_name')
    for r in qs:
        expected = (r.monthly_charge or Decimal(0)) * filters.months
        amount_paid = paid.get(r.id) or Decimal(0)
        balance = expected - amount_paid
        if balance <= 0:
            continue
        total_balance += balance
        rows.append({
            'owner': r.owner_name, 'contact': r.owners_contact or '', 'entity_type': labels.get(r.entity_type, r.entity_type),
            'area': r.area.name, 'ward': r.ward, 'village': r.village, 'house_number': r.house_number,
            'expected': expected, 'paid': amount_paid, 'balance': balance,
            'last_collection': timezone.localtime(r.last_collection_date) if r.last_collection_date else None,
        })
    rows.sort(key=lambda r: r['balance'], reverse=True)
    return ReportResult(
        title='Outstanding balances',
        subtitle=f"{filters.describe(_area_name(filters))} · {filters.months} billing month(s)",
        columns=[
            Column('owner', 'Owner'), Column('contact', 'Contact'), Column('entity_type', 'Type'),
            Column('area', 'Area'), Column('ward', 'Ward'), Column('village', 'Village / Mtaa'),
            Column('house_number', 'House no.'), Column('expected', 'Expected', 'money'),
            Column('paid', 'Paid', 'money'), Column('balance', 'Balance', 'money'),
            Column('last_collection', 'Last collection', 'datetime'),
        ],
        rows=rows,
        summary=[('Premises with balance', f"{len(rows):,}"), ('Total outstanding', money(total_balance))],
    )


@report('complaints', 'Complaints',
        'Complaints logged in the period with status, assignee and resolution time.',
        filters=('area_id', 'status', 'category_id'))
def complaints_report(filters: ReportFilters) -> ReportResult:
    from complaints.models import Complaint
    qs = Complaint.objects.select_related('category', 'area', 'assigned_to').filter(
        created_at__gte=filters.start_dt, created_at__lt=filters.end_dt,
    )
    if filters.area_id:
        qs = qs.filter(area_id=filters.area_id)
    if filters.status:
        qs = qs.filter(status=filters.status)
    if filters.category_id:
        qs = qs.filter(category_id=filters.category_id)
    statuses = dict(Complaint.STATUS_CHOICES)
    priorities = dict(Complaint.PRIORITY_CHOICES)
    rows, hours = [], []
    for c in qs.order_by('-created_at'):
        resolution_hours = None
        if c.resolved_at:
            resolution_hours = round((c.resolved_at - c.created_at).total_seconds() / 3600, 1)
            hours.append(resolution_hours)
        rows.append({
            'reference': c.reference, 'created_at': timezone.localtime(c.created_at),
            'category': c.category.name, 'title': c.title, 'area': c.area.name if c.area else '',
            'complainant': c.complainant_name, 'phone': c.complainant_phone,
            'priority': priorities.get(c.priority, c.priority), 'status': statuses.get(c.status, c.status),
            'assigned_to': _person(c.assigned_to), 'overdue': 'Yes' if c.is_overdue else '',
            'resolution_hours': resolution_hours,
        })
    open_count = sum(1 for c in rows if c['status'] in (statuses['open'], statuses['in_progress']))
    avg = round(sum(hours) / len(hours), 1) if hours else 0
    return ReportResult(
        title='Complaints',
        subtitle=filters.describe(_area_name(filters)),
        columns=[
            Column('reference', 'Reference'), Column('created_at', 'Logged', 'datetime'), Column('category', 'Category'),
            Column('title', 'Title'), Column('area', 'Area'), Column('complainant', 'Complainant'),
            Column('phone', 'Phone'), Column('priority', 'Priority'), Column('status', 'Status'),
            Column('assigned_to', 'Assigned to'), Column('overdue', 'Overdue'),
            Column('resolution_hours', 'Hours to resolve', 'number'),
        ],
        rows=rows,
        summary=[
            ('Complaints', f"{len(rows):,}"), ('Still open', f"{open_count:,}"),
            ('Overdue', f"{sum(1 for r in rows if r['overdue']):,}"), ('Avg. hours to resolve', str(avg)),
        ],
    )
