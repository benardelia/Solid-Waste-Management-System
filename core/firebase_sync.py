"""
Keeps Firebase in step with Django for users managed from the admin portal.

The mobile app reads the signed-in user's role and assigned area from the
Firestore `users/<uid>` document (see DataManager.getCurrentUserData), so any
role/area change made in Django must be mirrored there.
"""
import logging

import firebase_admin
from firebase_admin import auth, firestore

logger = logging.getLogger(__name__)


class FirebaseUnavailable(Exception):
    pass


def _require_app():
    # Importing core.firebase_auth initialises the default app if credentials exist.
    import core.firebase_auth  # noqa: F401
    if not firebase_admin._apps:
        raise FirebaseUnavailable('Firebase credentials are not configured on the server')


def firestore_profile(user):
    data = {
        'name': user.get_full_name() or user.username,
        'email': user.email,
        'role': user.user_type,
        'phone': user.phone or '',
    }
    data['assignedAreaId'] = str(user.assigned_area_id) if user.assigned_area_id else None
    return data


def create_firebase_user(*, email, password, display_name):
    """Creates the Firebase Auth account and returns its uid."""
    _require_app()
    try:
        record = auth.create_user(email=email, password=password, display_name=display_name or None)
    except auth.EmailAlreadyExistsError:
        raise ValueError('A Firebase account with this email already exists')
    except ValueError as exc:  # weak password, bad email
        raise ValueError(str(exc))
    return record.uid


def sync_user(user):
    """Best effort: push profile to Firestore and enabled/disabled state to Auth."""
    if not user.firebase_uid:
        return
    try:
        _require_app()
        firestore.client().collection('users').document(user.firebase_uid).set(firestore_profile(user), merge=True)
        auth.update_user(user.firebase_uid, disabled=not user.is_active,
                         display_name=user.get_full_name() or user.username)
    except FirebaseUnavailable:
        logger.warning('Firebase not configured; skipped sync for user %s', user.pk)
    except Exception:  # never block a Django save on Firebase being unreachable
        logger.exception('Failed to sync user %s to Firebase', user.pk)


def send_password_reset_link(email):
    _require_app()
    return auth.generate_password_reset_link(email)
