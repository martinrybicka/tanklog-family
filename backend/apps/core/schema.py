from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SessionScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.VersionedSessionAuthentication"
    name = "sessionAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": settings.SESSION_COOKIE_NAME}
