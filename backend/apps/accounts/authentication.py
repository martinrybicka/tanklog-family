import ipaddress

from django.contrib.auth import logout
from django.contrib.auth.backends import ModelBackend
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied

from apps.core.errors import Problem

from .models import User


def client_ip(request):
    # Hlavičce důvěřujeme jen v produkci za nepřístupným backendem a sanitizující proxy.
    from django.conf import settings

    value = request.META.get("HTTP_X_REAL_IP") if settings.SECURE_PROXY_SSL_HEADER else None
    try:
        return str(ipaddress.ip_address(value or request.META.get("REMOTE_ADDR", "127.0.0.1")))
    except ValueError:
        return "127.0.0.1"


class AccountBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or password is None:
            return None
        try:
            user = User.objects.get(username__iexact=username.strip())
        except User.DoesNotExist:
            User().set_password(password)
            return None
        valid = user.check_password(password)
        if not valid or not self.user_can_authenticate(user):
            return None
        if user.must_change_password and (
            user.temporary_password_consumed_at is not None
            or user.temporary_password_expires_at is None
            or user.temporary_password_expires_at <= timezone.now()
        ):
            return None
        return user


class VersionedSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        try:
            super().enforce_csrf(request)
        except PermissionDenied as error:
            raise Problem("csrf_failed", "Platnost formuláře vypršela. Obnovte stránku.", 403) from error

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, _ = result
        if request.session.get("auth_epoch") != user.auth_epoch:
            logout(request._request)
            raise Problem("authentication_required", "Přihlaste se znovu.", 403)
        return result
