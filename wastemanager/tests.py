from django.test import TestCase

from core.testing import gql, make_user
from wastemanager.models import CollectionRecord, ProjectArea, Registration

CREATE_REG = '''mutation($t:String!,$a:Int!,$uid:String){ createRegistration(entityType:$t, areaId:$a, ownerName:"Asha",
  district:"Dodoma Urban", ward:"Uhuru", village:"Kati", latitude:-6.1, longitude:35.7, wasteBinPresent:"yes", uid:$uid)
  { success registration { id entityType entityTypeLabel effectiveMonthlyFee } } }'''


class WasteManagerTests(TestCase):
    def setUp(self):
        self.area = ProjectArea.objects.create(name='Chamwino', monthly_fee=5000)
        self.worker = make_user('worker', 'worker', self.area)
        self.admin = make_user('admin', 'admin')

    def test_registration_validates_entity_type_and_returns_raw_code(self):
        self.assertIn('Unknown entity type', gql(CREATE_REG, self.worker, t='spaceship', a=self.area.id).errors[0])
        reg = gql(CREATE_REG, self.worker, t='household', a=self.area.id).data['createRegistration']['registration']
        self.assertEqual((reg['entityType'], reg['entityTypeLabel'], reg['effectiveMonthlyFee']), ('household', 'Household', 5000.0))

    def test_create_registration_is_idempotent_on_uid(self):
        uid = '4b1c8a4e-7d0c-4c1e-9d8a-2f1f6f0f3b11'
        a = gql(CREATE_REG, self.worker, t='shop', a=self.area.id, uid=uid).data['createRegistration']['registration']['id']
        b = gql(CREATE_REG, self.worker, t='shop', a=self.area.id, uid=uid).data['createRegistration']['registration']['id']
        self.assertEqual(a, b)
        self.assertEqual(Registration.objects.count(), 1)

    def test_log_collection_rejects_bad_status(self):
        q = 'mutation($a:Int!,$s:String!){ logCollection(areaId:$a, status:$s, amountCollected:100){ success collection { status } } }'
        self.assertTrue(gql(q, self.worker, a=self.area.id, s='teleported').errors)
        r = gql(q, self.worker, a=self.area.id, s='collected and paid')
        self.assertEqual(r.data['logCollection']['collection']['status'], 'collected and paid')

    def test_area_admin_crud(self):
        save = 'mutation($n:String!,$f:Float!,$id:Int){ saveProjectArea(id:$id, name:$n, monthlyFee:$f){ area { id name monthlyFee } } }'
        self.assertTrue(gql(save, self.worker, n='Kisasa', f=4000).errors)
        area = gql(save, self.admin, n='Kisasa', f=4000).data['saveProjectArea']['area']
        self.assertEqual(float(area['monthlyFee']), 4000)
        self.assertIn('already exists', gql(save, self.admin, n='chamwino', f=1).errors[0])
        delete = 'mutation($id:Int!){ deleteProjectArea(id:$id){ success } }'
        self.assertTrue(gql(delete, self.admin, id=int(area['id'])).data['deleteProjectArea']['success'])
        Registration.objects.create(owner_name='x', district='d', ward='w', village='v', waste_bin_present='no',
                                    latitude=0, longitude=0, area=self.area)
        self.assertIn('cannot be deleted', gql(delete, self.admin, id=self.area.id).errors[0])

    def test_update_registration_fee_override(self):
        reg = Registration.objects.create(owner_name='x', district='d', ward='w', village='v', waste_bin_present='no',
                                          latitude=0, longitude=0, area=self.area, number_of_units=3)
        q = 'mutation($id:Int!,$i:RegistrationInput!){ updateRegistration(id:$id, input:$i){ registration { monthlyFeeOverride effectiveMonthlyFee } } }'
        self.assertTrue(gql(q, self.worker, id=reg.id, i={'ownerName': 'y'}).errors)
        r = gql(q, self.admin, id=reg.id, i={'monthlyFeeOverride': 2500.5})
        self.assertFalse(r.errors, r.errors)
        self.assertEqual(r.data['updateRegistration']['registration']['effectiveMonthlyFee'], 7501.5)
        r = gql(q, self.admin, id=reg.id, i={'clearFeeOverride': True})
        self.assertIsNone(r.data['updateRegistration']['registration']['monthlyFeeOverride'])

    def test_dashboard_summary(self):
        reg = Registration.objects.create(owner_name='x', district='d', ward='w', village='v', waste_bin_present='no',
                                          latitude=0, longitude=0, area=self.area, number_of_units=2)
        from django.utils import timezone
        CollectionRecord.objects.create(worker=self.worker, area=self.area, registration=reg,
                                        timestamp=timezone.now(), status='collected', amount_collected=5000)
        q = '{ dashboardSummary { totalRegistrations visits expectedAmount collectedAmount collectionRate activeWorkers trend { visits } areas { areaName rate } registrationsByType { key count } } }'
        self.assertTrue(gql(q, self.worker).errors)
        d = gql(q, self.admin).data['dashboardSummary']
        self.assertEqual((d['totalRegistrations'], d['visits'], d['activeWorkers']), (1, 1, 1))
        self.assertEqual((d['expectedAmount'], d['collectedAmount'], d['collectionRate']), (10000.0, 5000.0, 50.0))
        self.assertEqual(sum(p['visits'] for p in d['trend']), 1)
