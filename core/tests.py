from django.test import TestCase

from core.testing import gql, make_user
from wastemanager.models import ProjectArea


class RolePermissionTests(TestCase):
    def setUp(self):
        self.area = ProjectArea.objects.create(name='Chamwino', monthly_fee=5000)
        self.admin = make_user('admin1', 'admin')
        self.worker = make_user('worker1', 'worker', self.area)

    def test_register_user_requires_admin(self):
        mutation = '''mutation { registerUser(username:"x", password:"pass12345", email:"x@x.com", userType:"admin") { success } }'''
        self.assertIn('Authentication required', gql(mutation).errors[0])
        self.assertIn('permission', gql(mutation, self.worker).errors[0])
        self.assertTrue(gql(mutation, self.admin).data['registerUser']['success'])

    def test_register_user_rejects_unknown_role(self):
        mutation = '''mutation { registerUser(username:"y", password:"pass12345", email:"y@x.com", userType:"boss") { success message } }'''
        self.assertFalse(gql(mutation, self.admin).data['registerUser']['success'])

    def test_worker_cannot_reassign(self):
        other = ProjectArea.objects.create(name='Miyuji', monthly_fee=3000)
        mutation = 'mutation($u:Int!,$a:Int!){ reassignWorker(userId:$u, areaId:$a){ success } }'
        self.assertTrue(gql(mutation, self.worker, u=self.worker.id, a=other.id).errors)
        self.assertTrue(gql(mutation, self.admin, u=self.worker.id, a=other.id).data['reassignWorker']['success'])
        self.worker.refresh_from_db()
        self.assertEqual(self.worker.assigned_area, other)

    def test_admin_update_user_and_self_protection(self):
        mutation = 'mutation($id:Int!,$active:Boolean,$role:String){ adminUpdateUser(id:$id, isActive:$active, userType:$role){ user { isActive userType } } }'
        r = gql(mutation, self.admin, id=self.worker.id, active=False, role='manager')
        self.assertEqual(r.data['adminUpdateUser']['user'], {'isActive': False, 'userType': 'manager'})
        self.assertIn('own account', gql(mutation, self.admin, id=self.admin.id, active=False).errors[0])

    def test_user_type_is_raw_string(self):
        r = gql('{ me { userType effectiveRole } }', self.worker)
        self.assertEqual(r.data['me'], {'userType': 'worker', 'effectiveRole': 'worker'})

    def test_superuser_counts_as_admin(self):
        su = make_user('root', 'worker', is_superuser=True)
        self.assertEqual(gql('{ me { effectiveRole } }', su).data['me']['effectiveRole'], 'admin')
