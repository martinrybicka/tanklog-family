import pytest
from django.test import override_settings

from .conftest import PASSWORD, csrf

pytestmark = pytest.mark.django_db


def test_https_csrf_origin_cookie_and_headers(users, client):
    with override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        CSRF_TRUSTED_ORIGINS=["https://testserver"],
    ):
        assert client.get("/api/v1/auth/me/").status_code == 301
        token = client.get("/api/v1/auth/csrf/", secure=True).json()["csrf_token"]
        body = {"username": "admin", "password": PASSWORD}
        url = "/api/v1/auth/login/"
        for origin in ["https://evil.invalid", "null", "http://testserver"]:
            response = client.post(
                url, body, format="json", secure=True, HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN=origin
            )
            assert response.status_code == 403 and response.json()["error"]["code"] == "csrf_failed"
        response = client.post(
            url, body, format="json", secure=True, HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://testserver"
        )
        assert response.status_code == 200
        assert response["Cache-Control"] == "private, no-store"
        assert response["X-Frame-Options"] == "DENY"
        assert response["X-Content-Type-Options"] == "nosniff"
        for name in ["sessionid", "csrftoken"]:
            assert client.cookies[name]["secure"] and client.cookies[name]["httponly"]
        assert client.get("/api/v1/vehicles/", secure=True).status_code == 200


def test_bad_host_and_bad_json_are_private_json(client):
    with override_settings(DEBUG=False):
        response = client.get("/api/v1/auth/csrf/", HTTP_HOST="evil.invalid")
        assert response.status_code == 400
        assert response["Content-Type"].startswith("application/json")
        assert response.json()["error"]["code"] == "bad_request"
        response = client.post(
            "/api/v1/auth/login/", "{invalid", content_type="application/json", HTTP_X_CSRFTOKEN=csrf(client)
        )
        assert response.status_code == 400 and response["Cache-Control"] == "private, no-store"


def test_forwarded_ip_is_ignored_without_trusted_proxy_configuration(client):
    from django.test import RequestFactory

    from apps.accounts.authentication import client_ip

    request = RequestFactory().get(
        "/", HTTP_X_REAL_IP="203.0.113.88", HTTP_X_FORWARDED_FOR="203.0.113.99", REMOTE_ADDR="127.0.0.1"
    )
    assert client_ip(request) == "127.0.0.1"
