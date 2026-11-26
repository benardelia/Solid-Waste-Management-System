import json
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.testing import gql, make_user
from reports.exporters import export
from reports.registry import REPORTS, ReportFilters, run_report
from wastemanager.models import CollectionRecord, ProjectArea, Registration


class ReportTests(TestCase):
    def setUp(self):
        self.area = ProjectArea.objects.create(name='Chamwino', monthly_fee=Decimal('5000'))
        self.worker = make_user('worker', 'worker', self.area, first_name='Juma')
        self.manager = make_user('manager', 'manager')
        base = dict(district='Dodoma Urban', ward='Uhuru', village='Kati', waste_bin_present='yes',
                    latitude=-6.1, longitude=35.7, area=self.area)
        self.paid = Registration.objects.create(owner_name='Asha', number_of_units=2, **base)
        self.unpaid = Registration.objects.create(owner_name='Baraka', entity_type='shop',
                                                  monthly_fee_override=Decimal('20000'), **base)
        now = timezone.now()
        CollectionRecord.objects.create(worker=self.worker, area=self.area, registration=self.paid,
                                        timestamp=now, status='collected', amount_collected=Decimal('10000'))
        CollectionRecord.objects.create(worker=self.worker, area=self.area, registration=self.unpaid,
                                        timestamp=now, status='missed', amount_collected=0)
        # outside the period, must be ignored
        CollectionRecord.objects.create(worker=self.worker, area=self.area, registration=self.unpaid,
                                        timestamp=now - timedelta(days=400), status='collected', amount_collected=99999)
        today = timezone.localdate()
        self.filters = ReportFilters(start_date=today.replace(day=1), end_date=today)

    def test_revenue_by_area_math(self):
        row = run_report('revenue_by_area', self.filters).rows[0]
        # Asha: 5000 × 2 units; Baraka: override 20000 × 1 unit
        self.assertEqual(row['expected'], Decimal('30000'))
        self.assertEqual(row['collected'], Decimal('10000'))
        self.assertEqual(row['outstanding'], Decimal('20000'))
        self.assertEqual(row['rate'], 33.3)
        self.assertEqual(row['missed'], 1)

    def test_defaulters_lists_only_balances(self):
        rows = run_report('defaulters', self.filters).rows
        self.assertEqual([r['owner'] for r in rows], ['Baraka'])
        self.assertEqual(rows[0]['balance'], Decimal('20000'))

    def test_every_report_exports_in_every_format(self):
        for key in REPORTS:
            result = run_report(key, self.filters)
            for fmt in ('csv', 'xlsx', 'pdf', 'json'):
                content, content_type, ext = export(result, fmt)
                self.assertTrue(content, f'{key}.{fmt} is empty')
            self.assertEqual(json.loads(export(result, 'json')[0])['title'], result.title)
        self.assertTrue(export(run_report('collections', self.filters), 'pdf')[0].startswith(b'%PDF'))
        self.assertTrue(export(run_report('collections', self.filters), 'xlsx')[0].startswith(b'PK'))

    def test_filter_validation(self):
        with self.assertRaises(ValueError):
            ReportFilters.from_params({'start_date': '2026-05-01', 'end_date': '2026-04-01'})
        self.assertEqual(ReportFilters.from_params({'start_date': '2026-01-15', 'end_date': '2026-03-01'}).months, 3)

    def test_graphql_preview_requires_report_role(self):
        q = '{ runReport(key:"collections") { title totalRows columns { key } displayRows summary { label value } } }'
        self.assertTrue(gql(q, self.worker).errors)
        r = gql(q, self.manager)
        self.assertFalse(r.errors, r.errors)
        self.assertEqual(r.data['runReport']['totalRows'], 2)
        self.assertEqual(r.data['runReport']['displayRows'][0]['amount'] in ('10,000', '0'), True)

    def test_rest_export_endpoint(self):
        client = APIClient()
        client.force_authenticate(self.worker)
        self.assertEqual(client.get('/api/reports/collections/export/?format=csv').status_code, 403)
        client.force_authenticate(self.manager)
        for fmt in ('pdf', 'xlsx', 'csv', 'json'):
            res = client.get(f'/api/reports/revenue_by_area/export/?format={fmt}')
            self.assertEqual(res.status_code, 200, fmt)
            self.assertIn(f'.{fmt}"', res['Content-Disposition'])
        self.assertEqual(client.get('/api/reports/nope/export/?format=pdf').status_code, 404)
        self.assertEqual(client.get('/api/reports/collections/export/?format=docx').status_code, 400)
        self.assertEqual(client.get('/api/reports/collections/export/?start_date=bad').status_code, 400)
        self.assertEqual(len(client.get('/api/reports/').json()['reports']), len(REPORTS))
