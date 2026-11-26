from django.test import TestCase

from core.testing import gql, make_user
from reference.models import EntityType


class ReferenceDataTests(TestCase):
    def test_seeded_lookups_are_public(self):
        r = gql('{ referenceData { entityTypes { code countsUnits } roles { code } paymentMethods { code } complaintCategories { code } } }')
        self.assertFalse(r.errors)
        codes = [e['code'] for e in r.data['referenceData']['entityTypes']]
        self.assertIn('household', codes)
        self.assertIn('manager', [x['code'] for x in r.data['referenceData']['roles']])
        self.assertTrue(r.data['referenceData']['complaintCategories'])

    def test_wards_by_district_name_case_insensitive(self):
        user = make_user('lo', 'land_officer')
        r = gql('{ wards(districtName:"DODOMA URBAN") { name postcode label } }', user)
        self.assertEqual(r.data['wards'][0], {'name': 'Uhuru', 'postcode': '41101', 'label': 'Uhuru, 41101'})

    def test_only_admin_saves_entity_types_and_inactive_hidden(self):
        mutation = 'mutation($i:EntityTypeInput!){ saveEntityType(input:$i){ entityType { code isActive } } }'
        data = {'code': 'Market', 'name': 'Market', 'isActive': False}
        self.assertTrue(gql(mutation, make_user('w', 'worker'), i=data).errors)
        r = gql(mutation, make_user('a', 'admin'), i=data)
        self.assertEqual(r.data['saveEntityType']['entityType'], {'code': 'market', 'isActive': False})
        visible = gql('{ referenceData { entityTypes { code } } }').data['referenceData']['entityTypes']
        self.assertNotIn('market', [e['code'] for e in visible])
        self.assertTrue(EntityType.objects.filter(code='market').exists())
