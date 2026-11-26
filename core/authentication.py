from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed


class FirebaseAuthentication(BaseAuthentication):
    """
    Accepts `Authorization: Bearer <Firebase ID token>` on REST endpoints, the
    same token the mobile app and admin portal already send to /graphql/.

    Tokens that are not Firebase tokens (e.g. SimpleJWT tokens) fall through to
    the next authentication class instead of failing outright.
    """

    keyword = b'bearer'

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if len(parts) != 2 or parts[0].lower() != self.keyword:
            return None
        token = parts[1].decode()
        # SimpleJWT tokens are signed HS256; Firebase ID tokens are RS256 with a `kid`.
        # Cheap check to avoid a network round-trip for non-Firebase tokens.
        if token.count('.') != 2:
            return None

        from core.firebase_auth import verify_firebase_token
        user = verify_firebase_token(token)
        if user is None:
            return None
        if not user.is_active:
            raise AuthenticationFailed('User account is disabled')
        return (user, token)

    def authenticate_header(self, request):
        return 'Bearer'
