import os
import subprocess
import sys

import pytest
from django.test import override_settings

from .conftest import PASSWORD, csrf, login, post


@pytest.mark.django_db
def test_admin_cannot_reset_own_account_into_inaccessible_state(admin_client, users):
    admin = users["admin"]
    detail = admin_client.get(f"/api/v1/admin/users/{admin.pk}/")
    response = post(
        admin_client,
        f"/api/v1/admin/users/{admin.pk}/password-reset/",
        {"current_password": PASSWORD},
        HTTP_IF_MATCH=detail["ETag"],
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "self_reset_forbidden"
    assert admin_client.get("/api/v1/profile/").status_code == 200


@pytest.mark.django_db
def test_cookie_flags_and_same_origin_policy(users, client):
    with override_settings(SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True):
        response = login(client)
        assert response.status_code == 200
        for key in ("sessionid", "csrftoken"):
            assert client.cookies[key]["secure"]
            assert client.cookies[key]["httponly"]
            assert client.cookies[key]["samesite"] == "Lax"
        assert response["X-Frame-Options"] == "DENY"
        assert "Access-Control-Allow-Origin" not in response


@pytest.mark.django_db
def test_authenticated_mutation_also_requires_csrf_and_forbids_mass_assignment(users, client):
    login(client, "user")
    detail = client.get("/api/v1/profile/")
    response = client.patch(
        "/api/v1/profile/", {"display_name": "Pokuste se"}, format="json", HTTP_IF_MATCH=detail["ETag"]
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    response = client.patch(
        "/api/v1/profile/",
        {"id": str(users["other"].pk), "is_active": True, "auth_epoch": 99},
        format="json",
        HTTP_IF_MATCH=detail["ETag"],
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "overrides",
    [
        {"DJANGO_DEBUG": "true"},
        {"DJANGO_SECURE_COOKIES": "false"},
        {"DJANGO_ALLOWED_HOSTS": "*"},
        {"DJANGO_CSRF_TRUSTED_ORIGINS": "http://localhost:8080"},
        {"DJANGO_SECRET_KEY": "weak"},
    ],
)
def test_production_refuses_unsafe_configuration(overrides):
    env = os.environ.copy()
    env.update(
        {
            "DJANGO_SECRET_KEY": "synthetic-test-only-production-validation-secret-1234567890",
            "DJANGO_DEBUG": "false",
            "DJANGO_SECURE_COOKIES": "true",
            "DJANGO_ALLOWED_HOSTS": "tanklog.example.invalid,127.0.0.1",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://tanklog.example.invalid",
        }
    )
    env.update(overrides)
    result = subprocess.run(
        [sys.executable, "-c", "import config.settings.production"], env=env, capture_output=True
    )
    assert result.returncode != 0
    assert b"ImproperlyConfigured" in result.stderr


@pytest.mark.django_db
def test_openapi_is_authenticated_json_and_describes_current_phase(admin_client):
    response = admin_client.get("/api/v1/admin/schema/")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")
    paths = response.json()["paths"]
    assert "/api/v1/auth/login/" in paths and "/api/v1/admin/users/" in paths
    assert "/api/v1/vehicles/" in paths and "/api/v1/admin/vehicles/" in paths
    assert "/api/v1/refuelings/" in paths and "/api/v1/refuelings/export/" in paths
    assert all("dashboard" not in path and "statistics" not in path for path in paths)


@pytest.mark.django_db
def test_saved_profile_and_theme_survive_cookie_deletion_and_new_device(users, client):
    from rest_framework.test import APIClient

    login(client, "user")
    detail = client.get("/api/v1/profile/")
    response = client.patch(
        "/api/v1/profile/",
        {"display_name": "Trvale uložené jméno", "theme": "DARK", "email": "test@example.invalid"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
        HTTP_IF_MATCH=detail["ETag"],
    )
    assert response.status_code == 200
    client.cookies.clear()
    assert client.get("/api/v1/profile/").status_code == 403
    assert login(client, "user").status_code == 200
    second_device = APIClient(enforce_csrf_checks=True)
    assert login(second_device, "user").status_code == 200
    for device in (client, second_device):
        profile = device.get("/api/v1/profile/").json()
        assert profile["display_name"] == "Trvale uložené jméno"
        assert profile["theme"] == "DARK"
        assert profile["email"] == "test@example.invalid"
    users["user"].refresh_from_db()
    assert users["user"].theme == "DARK"


@pytest.mark.django_db
def test_reauthentication_is_also_rate_limited(admin_client, users):
    target = users["user"]
    detail = admin_client.get(f"/api/v1/admin/users/{target.pk}/")
    for _ in range(5):
        response = post(
            admin_client,
            f"/api/v1/admin/users/{target.pk}/password-reset/",
            {"current_password": "incorrect"},
            HTTP_IF_MATCH=detail["ETag"],
        )
    assert response.status_code == 429
    response = post(
        admin_client,
        f"/api/v1/admin/users/{target.pk}/password-reset/",
        {"current_password": PASSWORD},
        HTTP_IF_MATCH=detail["ETag"],
    )
    assert response.status_code == 429
    target.refresh_from_db()
    assert target.check_password(PASSWORD) and not target.must_change_password
