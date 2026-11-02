import secrets
from datetime import timedelta

from django.contrib.auth import authenticate, login, logout, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, connection, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers

from apps.audit.models import record
from apps.core.errors import Problem

from .models import User


def etag(user):
    return f'"user:{user.pk}:{user.version}"'


def require_version(request, user):
    supplied = request.headers.get("If-Match")
    if not supplied:
        raise Problem("precondition_required", "Načtěte aktuální údaje před změnou.", 428)
    if supplied != etag(user):
        raise Problem("stale_version", "Údaje se mezitím změnily. Načtěte je znovu.", 412)


def check_session(request, user):
    if not user.is_active or user.auth_epoch != request.session.get("auth_epoch"):
        raise Problem("authentication_required", "Přihlaste se znovu.", 403)


def reauthenticate(request, user, password):
    # Také potvrzení citlivých akcí používá DB limit pokusů django-axes.
    authenticated = authenticate(
        request=getattr(request, "_request", request), username=user.username, password=password or ""
    )
    if authenticated is None or authenticated.pk != user.pk:
        record(request, "auth.reauthentication_failed", user)
        raise Problem("reauthentication_failed", "Aktuální heslo není správné.", 403)


def start_session(request, user, restricted=False):
    login(request, user, backend="apps.accounts.authentication.AccountBackend")
    request.session["auth_epoch"] = user.auth_epoch
    request.session["password_change_only"] = restricted
    request.session.set_expiry(15 * 60 if restricted else 12 * 60 * 60)


def sign_in(request, username, password):
    user = authenticate(request=request, username=username.strip().lower(), password=password)
    if user is None:
        record(request, "auth.login_failed")
        raise Problem("invalid_credentials", "Přihlašovací údaje nejsou správné nebo nejsou platné.", 403)
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        if not user.is_active or not user.check_password(password):
            raise Problem("invalid_credentials", "Přihlašovací údaje nejsou správné nebo nejsou platné.", 403)
        restricted = user.must_change_password
        if restricted:
            if (
                user.temporary_password_consumed_at
                or not user.temporary_password_expires_at
                or user.temporary_password_expires_at <= timezone.now()
            ):
                raise Problem(
                    "invalid_credentials", "Přihlašovací údaje nejsou správné nebo nejsou platné.", 403
                )
            user.set_unusable_password()
            user.temporary_password_consumed_at = timezone.now()
            user.version += 1
            user.save()
        start_session(request, user, restricted)
        record(request, "auth.login_temporary" if restricted else "auth.login", user, actor=user)
    return user


def change_password(request, data):
    # Neúspěšné pokusy se musejí uložit i při odmítnutí následné doménové operace.
    if not request.user.must_change_password:
        reauthenticate(request, request.user, data.get("current_password"))
    return _change_password_locked(request, data)


@transaction.atomic
def _change_password_locked(request, data):
    user = User.objects.select_for_update().get(pk=request.user.pk)
    check_session(request, user)
    if user.must_change_password and not request.session.get("password_change_only"):
        raise Problem("authentication_required", "Přihlaste se znovu.", 403)
    try:
        password_validation.validate_password(data["new_password"], user)
    except DjangoValidationError as error:
        raise serializers.ValidationError({"new_password": error.messages}) from error
    user.set_password(data["new_password"])
    user.must_change_password = False
    user.temporary_password_expires_at = None
    user.temporary_password_consumed_at = None
    user.auth_epoch += 1
    user.version += 1
    user.save()
    # Stará session nesmí zůstat použitelná na jiném zařízení.
    logout(request)
    start_session(request, user)
    record(request, "auth.password_changed", user, actor=user)
    return user


@transaction.atomic
def update_profile(request, data):
    user = User.objects.select_for_update().get(pk=request.user.pk)
    check_session(request, user)
    require_version(request, user)
    changes = {}
    for key, value in data.items():
        if getattr(user, key) != value:
            changes[key] = {"from": getattr(user, key), "to": value}
            setattr(user, key, value)
    if changes:
        user.version += 1
        user.save()
        record(request, "user.profile_updated", user, changes)
    return user


def lock_admin(request, target_id=None):
    # Jeden krátký transakční zámek serializuje změny správců i posledního ADMIN.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [2601101])
    ids = {request.user.pk, target_id} - {None}
    users = {user.pk: user for user in User.objects.select_for_update().filter(pk__in=ids).order_by("id")}
    actor = users[request.user.pk]
    check_session(request, actor)
    if actor.system_role != User.Role.ADMIN or actor.must_change_password:
        raise Problem("permission_denied", "Tato akce je pouze pro administrátora.", 403)
    target = users.get(target_id) if target_id else None
    if target_id and target is None:
        get_object_or_404(User, pk=target_id)
    return actor, target


def set_temporary_password(user):
    password = secrets.token_urlsafe(24)
    user.set_password(password)
    user.must_change_password = True
    user.temporary_password_consumed_at = None
    user.temporary_password_expires_at = timezone.now() + timedelta(hours=24)
    user.auth_epoch += 1
    user.version += 1
    return password


def ensure_admin_remains(user, *, active=None, role=None):
    active = user.is_active if active is None else active
    role = user.system_role if role is None else role
    if user.is_active and user.system_role == User.Role.ADMIN and (not active or role != User.Role.ADMIN):
        if not User.objects.filter(is_active=True, system_role=User.Role.ADMIN).exclude(pk=user.pk).exists():
            raise Problem(
                "last_administrator",
                "Posledního aktivního administrátora nelze deaktivovat ani zbavit role.",
                409,
            )


def create_account(request, data):
    reauthenticate(request, request.user, data["current_password"])
    return _create_account_locked(request, data)


@transaction.atomic
def _create_account_locked(request, data):
    lock_admin(request)
    data = {key: value for key, value in data.items() if key != "current_password"}
    user = User(**data)
    password = set_temporary_password(user)
    try:
        with transaction.atomic():
            user.save()
    except IntegrityError as error:
        raise serializers.ValidationError({"username": "Toto uživatelské jméno již existuje."}) from error
    record(request, "user.created", user, {"system_role": user.system_role})
    return user, password


def update_account(request, target_id, data):
    if "system_role" in data:
        reauthenticate(request, request.user, data.get("current_password"))
    return _update_account_locked(request, target_id, data)


@transaction.atomic
def _update_account_locked(request, target_id, data):
    _, user = lock_admin(request, target_id)
    require_version(request, user)
    data = {key: value for key, value in data.items() if key != "current_password"}
    if "system_role" in data:
        ensure_admin_remains(user, role=data["system_role"])
    changes = {}
    for key, value in data.items():
        if value != getattr(user, key):
            changes[key] = {"from": getattr(user, key), "to": value}
            setattr(user, key, value)
    if changes:
        if "system_role" in changes:
            user.auth_epoch += 1
            # Technická oprávnění nikdy nepřežijí odebrání aplikační role.
            if user.system_role != User.Role.ADMIN:
                user.is_staff = user.is_superuser = False
        user.version += 1
        user.save()
        record(request, "user.updated", user, changes)
    return user


def account_action(request, target_id, action, password):
    reauthenticate(request, request.user, password)
    return _account_action_locked(request, target_id, action)


@transaction.atomic
def _account_action_locked(request, target_id, action):
    actor, user = lock_admin(request, target_id)
    require_version(request, user)
    temporary = None
    if action == "password-reset":
        if user.pk == actor.pk:
            raise Problem(
                "self_reset_forbidden",
                "Vlastní heslo změňte v Nastavení. Tento reset je určen jiným účtům.",
                409,
            )
        if not user.is_active:
            raise Problem("inactive_account", "Nejdříve účet aktivujte.", 409)
        temporary = set_temporary_password(user)
    elif action == "deactivate":
        ensure_admin_remains(user, active=False)
        user.is_active = False
        user.auth_epoch += 1
        user.version += 1
    elif action == "activate":
        user.is_active = True
        user.auth_epoch += 1
        user.version += 1
    user.save()
    record(request, f"user.{action}", user)
    return user, temporary
