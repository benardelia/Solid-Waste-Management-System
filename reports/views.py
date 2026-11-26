from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import HasRole
from core.roles import REPORT_ROLES

from .exporters import FORMATS, export
from .registry import REPORTS, ReportFilters, run_report


class ReportListView(APIView):
    permission_classes = [IsAuthenticated, HasRole]
    allowed_roles = REPORT_ROLES

    def get(self, request):
        return Response({
            'formats': list(FORMATS),
            'reports': [
                {'key': d.key, 'title': d.title, 'description': d.description, 'filters': list(d.filters)}
                for d in REPORTS.values()
            ],
        })


class ReportExportView(APIView):
    """
    GET /api/reports/<key>/export/?format=xlsx&start_date=2026-11-01&end_date=2026-11-30&area_id=1

    Note: the query parameter is `file_format` or `format`; DRF reserves
    `format` for content negotiation so we read it ourselves.
    """
    permission_classes = [IsAuthenticated, HasRole]
    allowed_roles = REPORT_ROLES

    def perform_content_negotiation(self, request, force=False):
        # ?format=pdf would otherwise make DRF look for a "pdf" renderer and 404.
        return super().perform_content_negotiation(request, force=True)

    def get(self, request, key):
        if key not in REPORTS:
            return Response({'detail': f"Unknown report '{key}'"}, status=404)
        fmt = (request.query_params.get('file_format') or request.query_params.get('format') or 'pdf').lower()
        if fmt not in FORMATS:
            return Response({'detail': f"Unsupported format '{fmt}'"}, status=400)
        try:
            filters = ReportFilters.from_params(request.query_params)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)

        content, content_type, ext = export(run_report(key, filters), fmt)
        filename = f"{slugify(REPORTS[key].title)}_{filters.start_date}_{filters.end_date}.{ext}"
        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Cache-Control'] = 'no-store'
        return response
