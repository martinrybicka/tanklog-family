import pytest
from django.contrib.auth.hashers import make_password
from rest_framework.test import APIClient

from apps.accounts.models import User

PASSWORD = "Synthetic-Test-Account-2026!"
NEW_PASSWORD = "Synthetic-New-Password-2026!"


@pytest.fixture(scope="session")
def password_hash():
    return make_password(PASSWORD)


@pytest.fixture
def users(db, password_hash):
    return {
        "admin": User.objects.create(
            username="admin", display_name="Správce", system_role="ADMIN", password=password_hash
        ),
        "user": User.objects.create(username="user", display_name="Řidič", password=password_hash),
        "other": User.objects.create(username="other", password=password_hash),
    }


def csrf(client):
    return client.get("/api/v1/auth/csrf/").json()["csrf_token"]


def login(client, username="admin", password=PASSWORD):
    return client.post(
        "/api/v1/auth/login/",
        {"username": username, "password": password},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )


def post(client, path, data=None, **headers):
    return client.post(path, data or {}, format="json", HTTP_X_CSRFTOKEN=csrf(client), **headers)


@pytest.fixture
def client():
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def admin_client(users, client):
    assert login(client).status_code == 200
    return client
