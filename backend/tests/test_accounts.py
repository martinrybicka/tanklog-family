from datetime import timedelta

import pytest
from axes.models import AccessAttempt
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services import etag, set_temporary_password
from apps.audit.models import AuditEvent

from .conftest import NEW_PASSWORD, PASSWORD, csrf, login, post

pytestmark = pytest.mark.django_db


def test_anonymous_login_requires_csrf(client, users):
    response = client.post("/api/v1/auth/login/", {"username": "admin", "password": PASSWORD}, format="json")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    assert "sessionid" not in client.cookies


def test_login_rotates_session_and_csrf_and_logout_is_protected(client, users):
    before = csrf(client)
    assert login(client, "AdMiN").status_code == 200
    assert csrf(client) != before
    assert client.get("/api/v1/auth/me/").json()["system_role"] == "ADMIN"
    assert client.cookies["sessionid"]["httponly"]
    assert client.post("/api/v1/auth/logout/", {}, format="json").status_code == 403
    assert post(client, "/api/v1/auth/logout/").status_code == 204
    assert client.get("/api/v1/auth/me/").status_code == 403
    assert post(client, "/api/v1/auth/logout/").status_code == 204


@pytest.mark.parametrize(
    "path", ["profile/", "admin/users/", "admin/system/", "admin/audit/", "admin/schema/"]
)
def test_anonymous_cannot_read_private_endpoints(client, path):
    response = client.get("/api/v1/" + path)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "authentication_required"
    assert response["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("path", ["admin/users/", "admin/system/", "admin/audit/", "admin/schema/"])
def test_user_cannot_access_admin(users, client, path):
    assert login(client, "user").status_code == 200
    assert client.get("/api/v1/" + path).status_code == 403


def test_profile_whitelist_csrf_and_optimistic_version(users, client):
    login(client, "user")
    detail = client.get("/api/v1/profile/")
    headers = {"HTTP_X_CSRFTOKEN": csrf(client), "HTTP_IF_MATCH": detail["ETag"]}
    assert (
        client.patch("/api/v1/profile/", {"system_role": "ADMIN"}, format="json", **headers).status_code
        == 400
    )
    assert (
        client.patch(
            "/api/v1/profile/", {"display_name": "Nové jméno"}, format="json", HTTP_X_CSRFTOKEN=csrf(client)
        ).status_code
        == 428
    )
    assert (
        client.patch("/api/v1/profile/", {"display_name": "Nové jméno"}, format="json", **headers).status_code
        == 200
    )
    assert (
        client.patch("/api/v1/profile/", {"display_name": "Přepis"}, format="json", **headers).status_code
        == 412
    )
    assert client.get("/api/v1/profile/").json()["display_name"] == "Nové jméno"
    assert (
        client.patch(
            "/api/v1/profile/",
            {"email": "bad"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf(client),
            HTTP_IF_MATCH=client.get("/api/v1/profile/")["ETag"],
        ).status_code
        == 400
    )


def create_account(client, **overrides):
    data = {
        "username": "new-driver",
        "display_name": "Nový řidič",
        "system_role": "USER",
        "current_password": PASSWORD,
    }
    data.update(overrides)
    return post(client, "/api/v1/admin/users/", data)


def test_create_account_hash_secret_once_and_force_change(admin_client):
    response = create_account(admin_client)
    assert response.status_code == 201, response.data
    secret = response.json()["temporary_password"]
    user = User.objects.get(username="new-driver")
    assert user.check_password(secret)
    assert user.password != secret and user.must_change_password
    assert timedelta(hours=23) < user.temporary_password_expires_at - timezone.now() <= timedelta(hours=24)
    assert secret not in str(admin_client.get(f"/api/v1/admin/users/{user.pk}/").json())
    assert secret not in str(list(AuditEvent.objects.values()))
    assert response["Cache-Control"] == "private, no-store"
    restricted = APIClient(enforce_csrf_checks=True)
    assert login(restricted, user.username, secret).status_code == 200
    assert restricted.get("/api/v1/auth/me/").json() == {
        "id": str(user.pk),
        "username": user.username,
        "must_change_password": True,
    }
    for path in ["profile/", "admin/users/", "admin/system/", "admin/schema/"]:
        denial = restricted.get("/api/v1/" + path)
        assert denial.status_code == 403 and denial.json()["error"]["code"] == "password_change_required"
    replay = APIClient(enforce_csrf_checks=True)
    assert login(replay, user.username, secret).status_code == 403
    assert post(restricted, "/api/v1/auth/password/change/", {"new_password": "short"}).status_code == 400
    assert (
        post(restricted, "/api/v1/auth/password/change/", {"new_password": NEW_PASSWORD}).status_code == 200
    )
    assert restricted.get("/api/v1/profile/").status_code == 200
    assert login(replay, user.username, NEW_PASSWORD).status_code == 200


def test_restricted_admin_cannot_reach_admin_apis(admin_client):
    response = create_account(admin_client, username="new-admin", system_role="ADMIN")
    restricted = APIClient(enforce_csrf_checks=True)
    login(restricted, "new-admin", response.json()["temporary_password"])
    assert restricted.get("/api/v1/admin/users/").status_code == 403


def test_temporary_password_expiry_and_restricted_session_expiry(admin_client):
    response = create_account(admin_client)
    user = User.objects.get(username="new-driver")
    User.objects.filter(pk=user.pk).update(
        temporary_password_expires_at=timezone.now() - timedelta(seconds=1)
    )
    c = APIClient(enforce_csrf_checks=True)
    assert login(c, user.username, response.json()["temporary_password"]).status_code == 403
    user.refresh_from_db()
    secret = set_temporary_password(user)
    user.save()
    assert login(c, user.username, secret).status_code == 200
    session = c.session
    session.set_expiry(timezone.now() - timedelta(seconds=1))
    session.save()
    assert post(c, "/api/v1/auth/password/change/", {"new_password": NEW_PASSWORD}).status_code == 403
    assert login(c, user.username, secret).status_code == 403


def test_reset_revokes_old_sessions_and_prior_temporary(admin_client, users):
    c = APIClient(enforce_csrf_checks=True)
    assert login(c, "user").status_code == 200
    target = users["user"]
    detail = admin_client.get(f"/api/v1/admin/users/{target.pk}/")
    first = post(
        admin_client,
        f"/api/v1/admin/users/{target.pk}/password-reset/",
        {"current_password": PASSWORD},
        HTTP_IF_MATCH=detail["ETag"],
    )
    assert first.status_code == 200
    assert c.get("/api/v1/profile/").status_code == 403
    detail = admin_client.get(f"/api/v1/admin/users/{target.pk}/")
    second = post(
        admin_client,
        f"/api/v1/admin/users/{target.pk}/password-reset/",
        {"current_password": PASSWORD},
        HTTP_IF_MATCH=detail["ETag"],
    )
    assert login(c, "user", first.json()["temporary_password"]).status_code == 403
    assert login(c, "user", second.json()["temporary_password"]).status_code == 200


def test_password_change_revokes_other_sessions(users, client):
    other = APIClient(enforce_csrf_checks=True)
    assert login(client, "user").status_code == login(other, "user").status_code == 200
    assert (
        post(
            client, "/api/v1/auth/password/change/", {"new_password": NEW_PASSWORD, "current_password": "bad"}
        ).status_code
        == 403
    )
    assert (
        post(
            client,
            "/api/v1/auth/password/change/",
            {"new_password": NEW_PASSWORD, "current_password": PASSWORD},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/profile/").status_code == 200
    assert other.get("/api/v1/profile/").status_code == 403


def test_deactivation_and_activation_do_not_restore_sessions(admin_client, users):
    target = users["user"]
    c = APIClient(enforce_csrf_checks=True)
    login(c, "user")
    for action in ["deactivate", "activate"]:
        detail = admin_client.get(f"/api/v1/admin/users/{target.pk}/")
        response = post(
            admin_client,
            f"/api/v1/admin/users/{target.pk}/{action}/",
            {"current_password": PASSWORD},
            HTTP_IF_MATCH=detail["ETag"],
        )
        assert response.status_code == 200
        assert c.get("/api/v1/profile/").status_code == 403
        if action == "deactivate":
            assert login(c, "user").status_code == 403
    assert login(c, "user").status_code == 200


def test_admin_creation_requires_reauthentication_and_case_insensitive_username(admin_client):
    assert create_account(admin_client, current_password="bad").status_code == 403
    assert create_account(admin_client, username="ADMIN").status_code == 400
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create(username="ADMIN")


def test_last_admin_is_protected_and_role_changes_revoke_session(admin_client, users):
    admin = users["admin"]
    detail = admin_client.get(f"/api/v1/admin/users/{admin.pk}/")
    assert (
        post(
            admin_client,
            f"/api/v1/admin/users/{admin.pk}/deactivate/",
            {"current_password": PASSWORD},
            HTTP_IF_MATCH=detail["ETag"],
        ).status_code
        == 409
    )
    response = admin_client.patch(
        f"/api/v1/admin/users/{admin.pk}/",
        {"system_role": "USER", "current_password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(admin_client),
        HTTP_IF_MATCH=detail["ETag"],
    )
    assert response.status_code == 409
    target = users["user"]
    c = APIClient(enforce_csrf_checks=True)
    login(c, "user")
    response = admin_client.patch(
        f"/api/v1/admin/users/{target.pk}/",
        {"system_role": "ADMIN", "current_password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(admin_client),
        HTTP_IF_MATCH=etag(target),
    )
    assert response.status_code == 200
    assert c.get("/api/v1/admin/users/").status_code == 403
    assert login(c, "user").status_code == 200
    assert c.get("/api/v1/admin/users/").status_code == 200


def test_login_rate_limit_is_database_persistent(users, client):
    for _ in range(5):
        response = post(client, "/api/v1/auth/login/", {"username": "user", "password": "invalid"})
    assert response.status_code == 429
    assert response["Retry-After"] == "900"
    assert AccessAttempt.objects.filter(username="user").exists()
    assert login(APIClient(enforce_csrf_checks=True), "USER").status_code == 429
    # Podvržená IP nesmí ve vývoji obejít limit.
    assert (
        post(
            client,
            "/api/v1/auth/login/",
            {"username": "user", "password": PASSWORD},
            HTTP_X_REAL_IP="198.51.100.10",
            HTTP_X_FORWARDED_FOR="198.51.100.10",
        ).status_code
        == 429
    )
    assert login(client, "other").status_code == 200


def test_filters_pagination_audit_and_no_public_signup(admin_client):
    response = admin_client.get("/api/v1/admin/users/?system_role=USER&page_size=1")
    assert response.json()["count"] == 2 and len(response.json()["results"]) == 1
    assert admin_client.get("/api/v1/admin/users/?page_size=101").status_code == 400
    assert admin_client.get("/api/v1/admin/users/?unknown=true").status_code == 400
    assert admin_client.get("/api/v1/admin/audit/?action=auth.login").json()["count"] >= 1
    assert (
        admin_client.post(
            "/api/v1/admin/audit/", {}, format="json", HTTP_X_CSRFTOKEN=csrf(admin_client)
        ).status_code
        == 405
    )
    assert admin_client.get("/api/v1/register/").status_code == 404
    assert "SECRET_KEY" not in str(admin_client.get("/api/v1/admin/system/").json())


def test_csrf_origin_rejection_and_error_request_id(users, client):
    response = post(
        client,
        "/api/v1/auth/login/",
        {"username": "admin", "password": PASSWORD},
        HTTP_ORIGIN="https://evil.invalid",
    )
    assert response.status_code == 403
    assert response.json()["error"]["request_id"] == response["X-Request-ID"]
