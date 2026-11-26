import graphene
from graphene.types.generic import GenericScalar
from graphql import GraphQLError

from core.permissions import require_roles
from core.roles import REPORT_ROLES

from .exporters import FORMATS, display, json_value
from .registry import REPORTS, ReportFilters, run_report

PREVIEW_ROW_LIMIT = 1000


class ReportDefinitionType(graphene.ObjectType):
    key = graphene.String(required=True)
    title = graphene.String(required=True)
    description = graphene.String(required=True)
    filters = graphene.List(graphene.NonNull(graphene.String), required=True)


class ReportColumnType(graphene.ObjectType):
    key = graphene.String(required=True)
    label = graphene.String(required=True)
    kind = graphene.String(required=True)


class ReportSummaryItemType(graphene.ObjectType):
    label = graphene.String(required=True)
    value = graphene.String(required=True)


class ReportResultType(graphene.ObjectType):
    title = graphene.String(required=True)
    subtitle = graphene.String(required=True)
    columns = graphene.List(graphene.NonNull(ReportColumnType), required=True)
    rows = GenericScalar(description='List of {columnKey: raw value}', required=True)
    display_rows = GenericScalar(description='List of {columnKey: formatted text}', required=True)
    summary = graphene.List(graphene.NonNull(ReportSummaryItemType), required=True)
    total_rows = graphene.Int(required=True)
    truncated = graphene.Boolean(required=True)


class ReportFiltersInput(graphene.InputObjectType):
    start_date = graphene.Date()
    end_date = graphene.Date()
    area_id = graphene.Int()
    worker_id = graphene.Int()
    status = graphene.String()
    entity_type = graphene.String()
    category_id = graphene.Int()


class ReportQueries(graphene.ObjectType):
    report_definitions = graphene.List(graphene.NonNull(ReportDefinitionType), required=True)
    report_formats = graphene.List(graphene.NonNull(graphene.String), required=True)
    run_report = graphene.Field(
        ReportResultType, key=graphene.String(required=True), filters=ReportFiltersInput(),
    )

    @staticmethod
    @require_roles(*REPORT_ROLES)
    def resolve_report_definitions(root, info):
        return [ReportDefinitionType(key=d.key, title=d.title, description=d.description, filters=list(d.filters))
                for d in REPORTS.values()]

    @staticmethod
    def resolve_report_formats(root, info):
        return list(FORMATS)

    @staticmethod
    @require_roles(*REPORT_ROLES)
    def resolve_run_report(root, info, key, filters=None):
        if key not in REPORTS:
            raise GraphQLError(f"Unknown report '{key}'")
        try:
            parsed = ReportFilters.from_params(dict(filters or {}))
        except ValueError as exc:
            raise GraphQLError(str(exc))
        result = run_report(key, parsed)
        rows = result.rows[:PREVIEW_ROW_LIMIT]
        return ReportResultType(
            title=result.title,
            subtitle=result.subtitle,
            columns=[ReportColumnType(key=c.key, label=c.label, kind=c.kind) for c in result.columns],
            rows=[{c.key: json_value(r.get(c.key)) for c in result.columns} for r in rows],
            display_rows=[{c.key: display(r.get(c.key), c.kind) for c in result.columns} for r in rows],
            summary=[ReportSummaryItemType(label=l, value=v) for l, v in result.summary],
            total_rows=len(result.rows),
            truncated=len(result.rows) > PREVIEW_ROW_LIMIT,
        )
