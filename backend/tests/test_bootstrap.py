import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Installation, User
from apps.audit.models import AuditEvent

from .conftest import PASSWORD, post

pytestmark = pytest.mark.django_db
TOKEN = "synthetic-one-time-installation-code-123456789"


def payload(**changes):
    return {
        "setup_token": TOKEN,
        "username": "FamilyAdmin",
        "display_name": "Správce",
        "password": PASSWORD,
        "password_confirmation": PASSWORD,
        **changes,
    }


def test_first_admin_requires_csrf_and_secret_then_creates_session_once(client, settings):
    settings.TANKLOG_SETUP_TOKEN = TOKEN
    path = "/api/v1/auth/setup/"
    assert client.get(path).json()["available"]
    assert client.post(path, payload(), format="json").status_code == 403
    assert post(client, path, payload(setup_token="wrong")).status_code == 403
    assert not User.objects.exists()
    assert post(client, path, payload(password_confirmation="wrong")).status_code == 400
    response = post(client, path, payload())
    assert response.status_code == 201 and response.json()["system_role"] == "ADMIN"
    assert User.objects.count() == 1 and User.objects.get().username == "familyadmin"
    assert client.get("/api/v1/auth/me/").status_code == 200
    assert not client.get(path).json()["available"]
    other = APIClient(enforce_csrf_checks=True)
    assert post(other, path, payload(username="hacker")).status_code == 409
    assert User.objects.count() == 1 and Installation.objects.count() == 1
    assert TOKEN not in str(list(AuditEvent.objects.values("changes")))
    assert PASSWORD not in str(list(AuditEvent.objects.values("changes")))


def test_setup_disabled_without_secret_or_with_existing_accounts(client, settings, users):
    settings.TANKLOG_SETUP_TOKEN = TOKEN
    assert not client.get("/api/v1/auth/setup/").json()["available"]
    assert post(client, "/api/v1/auth/setup/", payload()).status_code == 409


def test_empty_installation_without_token_is_not_public_registration(client, settings):
    settings.TANKLOG_SETUP_TOKEN = ""
    assert not client.get("/api/v1/auth/setup/").json()["available"]
    assert post(client, "/api/v1/auth/setup/", payload()).status_code == 409


def test_completed_marker_prevents_reopening_without_users(client, settings):
    from django.utils import timezone

    settings.TANKLOG_SETUP_TOKEN = TOKEN
    Installation.objects.create(completed_at=timezone.now())
    assert not client.get("/api/v1/auth/setup/").json()["available"]
    assert post(client, "/api/v1/auth/setup/", payload()).status_code == 409
