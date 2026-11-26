from django.test import TestCase

from complaints.models import Complaint, ComplaintCategory
from core.testing import gql, make_user
from wastemanager.models import ProjectArea

CREATE = '''mutation($c:Int!,$a:Int){ createComplaint(categoryId:$c, title:"Bin overflowing", description:"Since Monday",
  areaId:$a, complainantName:"Asha", complainantPhone:"0712000000") { complaint { id reference status priority dueAt } } }'''
STATUS = 'mutation($id:Int!,$s:String!,$m:String){ updateComplaintStatus(id:$id, status:$s, message:$m){ complaint { status resolvedAt } } }'


class ComplaintFlowTests(TestCase):
    def setUp(self):
        self.area = ProjectArea.objects.create(name='Chamwino', monthly_fee=5000)
        self.other_area = ProjectArea.objects.create(name='Miyuji', monthly_fee=5000)
        self.officer = make_user('officer', 'env_officer')
        self.worker = make_user('worker', 'worker', self.area)
        self.outsider = make_user('outsider', 'worker', self.other_area)
        self.category = ComplaintCategory.objects.get(code='overflowing-bin')

    def create(self, user):
        r = gql(CREATE, user, c=self.category.id, a=self.area.id)
        self.assertFalse(r.errors, r.errors)
        return r.data['createComplaint']['complaint']

    def test_create_sets_reference_priority_and_sla(self):
        c = self.create(self.worker)
        self.assertRegex(c['reference'], r'^CMP-\d{6}-0001$')
        self.assertEqual((c['status'], c['priority']), ('open', 'high'))
        self.assertIsNotNone(c['dueAt'])
        self.assertRegex(self.create(self.worker)['reference'], r'-0002$')

    def test_visibility_is_scoped_for_workers(self):
        self.create(self.officer)
        q = '{ complaints { items { reference } pagination { totalCount } } }'
        self.assertEqual(gql(q, self.worker).data['complaints']['pagination']['totalCount'], 1)  # same area
        self.assertEqual(gql(q, self.outsider).data['complaints']['pagination']['totalCount'], 0)
        self.assertEqual(gql(q, self.officer).data['complaints']['pagination']['totalCount'], 1)

    def test_lifecycle_assign_resolve_close(self):
        cid = int(self.create(self.officer)['id'])
        # an unassigned worker can't change status
        self.assertTrue(gql(STATUS, self.worker, id=cid, s='resolved', m='done').errors)
        r = gql('mutation($id:Int!,$u:Int){ assignComplaint(id:$id, userId:$u){ complaint { status assignedTo { username } } } }',
                self.officer, id=cid, u=self.worker.id)
        self.assertEqual(r.data['assignComplaint']['complaint']['status'], 'in_progress')
        # resolving needs an explanation
        self.assertIn('describe', gql(STATUS, self.worker, id=cid, s='resolved').errors[0])
        r = gql(STATUS, self.worker, id=cid, s='resolved', m='Emptied the bin')
        self.assertIsNotNone(r.data['updateComplaintStatus']['complaint']['resolvedAt'])
        # worker can't close; supervisor can
        self.assertTrue(gql(STATUS, self.worker, id=cid, s='closed').errors)
        self.assertEqual(gql(STATUS, self.officer, id=cid, s='closed').data['updateComplaintStatus']['complaint']['status'], 'closed')
        complaint = Complaint.objects.get(id=cid)
        self.assertEqual(complaint.resolution_notes, 'Emptied the bin')
        self.assertEqual(complaint.updates.count(), 4)  # logged, assigned, resolved, closed

    def test_internal_comments_hidden_from_workers(self):
        cid = int(self.create(self.officer)['id'])
        gql('mutation($id:Int!){ addComplaintComment(id:$id, message:"check billing", isInternal:true){ success } }', self.officer, id=cid)
        gql('mutation($id:Int!){ addComplaintComment(id:$id, message:"on my way"){ success } }', self.worker, id=cid)
        q = 'query($id:Int!){ complaint(id:$id){ updates { message } } }'
        officer_msgs = [u['message'] for u in gql(q, self.officer, id=cid).data['complaint']['updates']]
        worker_msgs = [u['message'] for u in gql(q, self.worker, id=cid).data['complaint']['updates']]
        self.assertIn('check billing', officer_msgs)
        self.assertNotIn('check billing', worker_msgs)
        self.assertIn('on my way', worker_msgs)

    def test_stats(self):
        self.create(self.officer)
        r = gql('{ complaintStats { total open byCategory { key count } } }', self.officer)
        self.assertEqual(r.data['complaintStats']['open'], 1)
        self.assertEqual(r.data['complaintStats']['byCategory'][0], {'key': 'overflowing-bin', 'count': 1})
