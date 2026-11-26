import graphene
from django.db import transaction
from graphql import GraphQLError

from core.models import User
from core import firebase_sync
from core.permissions import require_roles
from core.roles import ROLE_CODES, USER_MANAGER_ROLES, WORKER_ASSIGNER_ROLES
from wastemanager.models import ProjectArea
from core.graphql.types.user import UserType

class RegisterUser(graphene.Mutation):
    class Arguments:
        username = graphene.String(required=True)
        password = graphene.String(required=True)
        email = graphene.String(required=True)
        first_name = graphene.String()
        last_name = graphene.String()
        phone = graphene.String()
        user_type = graphene.String()

    user = graphene.Field(UserType)
    success = graphene.Boolean()
    message = graphene.String()

    @require_roles(*USER_MANAGER_ROLES)
    def mutate(self, info, username, password, email, **kwargs):
        # Previously unauthenticated: anyone could create an admin account.
        if kwargs.get('user_type') and kwargs['user_type'] not in ROLE_CODES:
            return RegisterUser(success=False, message="Invalid role")
        if User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
            return RegisterUser(success=False, message="Username or Email already exists")
        
        user = User(
            username=username,
            email=email,
            first_name=kwargs.get('first_name', ''),
            last_name=kwargs.get('last_name', ''),
            phone=kwargs.get('phone', ''),
            user_type=kwargs.get('user_type', 'worker')
        )
        user.set_password(password)
        user.save()
        return RegisterUser(user=user, success=True, message="User registered successfully")


class ReassignWorker(graphene.Mutation):
    """Reassign a worker (or any user) to a different project area."""
    class Arguments:
        user_id = graphene.Int(required=True, description="Django DB user ID")
        area_id = graphene.Int(required=True, description="Target ProjectArea ID")

    success = graphene.Boolean()
    message = graphene.String()
    user    = graphene.Field(UserType)

    @staticmethod
    @require_roles(*WORKER_ASSIGNER_ROLES)
    def mutate(root, info, user_id, area_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return ReassignWorker(success=False, message=f"User {user_id} not found")

        try:
            area = ProjectArea.objects.get(id=area_id)
        except ProjectArea.DoesNotExist:
            return ReassignWorker(success=False, message=f"Area {area_id} not found")

        user.assigned_area = area
        user.save(update_fields=['assigned_area'])
        firebase_sync.sync_user(user)  # the mobile app reads assignedAreaId from Firestore
        return ReassignWorker(success=True, message="Worker reassigned successfully", user=user)


def _validate_profile(role=None, area_id=None):
    if role is not None and role not in ROLE_CODES:
        raise GraphQLError(f'Invalid role "{role}"')
    if area_id and not ProjectArea.objects.filter(id=area_id).exists():
        raise GraphQLError('Project area not found')


def _unique_username(email):
    base = email.split('@')[0][:140] or 'user'
    username, n = base, 1
    while User.objects.filter(username=username).exists():
        username, n = f'{base}{n}', n + 1
    return username


class AdminCreateUser(graphene.Mutation):
    """
    Creates the Firebase Auth account, the Firestore profile the mobile app
    reads, and the Django user, in one step. The new user can sign in to the
    mobile app or the portal straight away.
    """

    class Arguments:
        email = graphene.String(required=True)
        password = graphene.String(required=True)
        first_name = graphene.String(required=True)
        last_name = graphene.String(default_value='')
        phone = graphene.String(default_value='')
        user_type = graphene.String(required=True)
        assigned_area_id = graphene.Int()

    user = graphene.Field(UserType)
    success = graphene.Boolean()
    message = graphene.String()

    @require_roles(*USER_MANAGER_ROLES)
    def mutate(self, info, email, password, first_name, user_type, last_name='', phone='', assigned_area_id=None):
        email = email.strip().lower()
        _validate_profile(user_type, assigned_area_id)
        if len(password) < 8:
            raise GraphQLError('Password must be at least 8 characters')
        if User.objects.filter(email__iexact=email).exists():
            raise GraphQLError('A user with this email already exists')

        display_name = f'{first_name} {last_name}'.strip()
        try:
            uid = firebase_sync.create_firebase_user(email=email, password=password, display_name=display_name)
        except (ValueError, firebase_sync.FirebaseUnavailable) as exc:
            raise GraphQLError(str(exc))

        with transaction.atomic():
            user = User(
                username=_unique_username(email), email=email, first_name=first_name.strip(),
                last_name=last_name.strip(), phone=phone.strip(), user_type=user_type,
                assigned_area_id=assigned_area_id, firebase_uid=uid,
            )
            user.set_unusable_password()  # authentication happens in Firebase
            user.save()
        firebase_sync.sync_user(user)
        return AdminCreateUser(user=user, success=True, message='User created')


class AdminUpdateUser(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        first_name = graphene.String()
        last_name = graphene.String()
        phone = graphene.String()
        user_type = graphene.String()
        assigned_area_id = graphene.Int()
        clear_area = graphene.Boolean()
        is_active = graphene.Boolean()

    user = graphene.Field(UserType)
    success = graphene.Boolean()

    @require_roles(*USER_MANAGER_ROLES)
    def mutate(self, info, id, clear_area=False, **fields):
        user = User.objects.filter(id=id).first()
        if user is None:
            raise GraphQLError('User not found')
        _validate_profile(fields.get('user_type'), fields.get('assigned_area_id'))
        me = info.context.user
        if user.id == me.id and (fields.get('is_active') is False or fields.get('user_type') not in (None, 'admin')):
            raise GraphQLError('You cannot deactivate or demote your own account')
        for key, value in fields.items():
            if value is not None:
                setattr(user, key, value.strip() if isinstance(value, str) else value)
        if clear_area:
            user.assigned_area = None
        user.save()
        firebase_sync.sync_user(user)
        return AdminUpdateUser(user=user, success=True)


class SendPasswordReset(graphene.Mutation):
    class Arguments:
        user_id = graphene.Int(required=True)

    success = graphene.Boolean()
    link = graphene.String(description='Firebase reset link to share with the user')

    @require_roles(*USER_MANAGER_ROLES)
    def mutate(self, info, user_id):
        user = User.objects.filter(id=user_id).first()
        if user is None or not user.email:
            raise GraphQLError('User not found')
        try:
            link = firebase_sync.send_password_reset_link(user.email)
        except Exception as exc:
            raise GraphQLError(f'Could not create reset link: {exc}')
        return SendPasswordReset(success=True, link=link)


class CoreMutation(graphene.ObjectType):
    register_user   = RegisterUser.Field()
    reassign_worker = ReassignWorker.Field()
    admin_create_user = AdminCreateUser.Field()
    admin_update_user = AdminUpdateUser.Field()
    send_password_reset = SendPasswordReset.Field()
