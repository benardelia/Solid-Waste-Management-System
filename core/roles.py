"""
Single source of truth for user roles.

The mobile app and the admin portal both read this list through the
`referenceData` GraphQL query, so adding a role here is enough to make it
selectable everywhere.
"""

ADMIN = 'admin'
LAND_OFFICER = 'land_officer'
ENV_OFFICER = 'env_officer'
MANAGER = 'manager'
WORKER = 'worker'

ROLE_CHOICES = [
    (ADMIN, 'Admin'),
    (LAND_OFFICER, 'Land Officer'),
    (ENV_OFFICER, 'Environment Officer'),
    (MANAGER, 'Manager'),
    (WORKER, 'Worker'),
]

ROLE_CODES = [code for code, _ in ROLE_CHOICES]

# Groups of roles used by permission checks.
STAFF_ROLES = (ADMIN, ENV_OFFICER, MANAGER, LAND_OFFICER)   # can use the admin portal
REPORT_ROLES = (ADMIN, ENV_OFFICER, MANAGER)                # can run and export reports
COMPLAINT_MANAGER_ROLES = (ADMIN, ENV_OFFICER, MANAGER, LAND_OFFICER)
USER_MANAGER_ROLES = (ADMIN,)
REFERENCE_MANAGER_ROLES = (ADMIN,)
AREA_MANAGER_ROLES = (ADMIN, ENV_OFFICER, MANAGER)
WORKER_ASSIGNER_ROLES = (ADMIN, ENV_OFFICER, MANAGER, LAND_OFFICER)


def user_role(user):
    """Effective role; superusers are always treated as admins."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    if user.is_superuser:
        return ADMIN
    return user.user_type


def has_role(user, roles):
    return user_role(user) in roles
