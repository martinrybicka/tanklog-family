from unittest.mock import patch

import pytest

from apps.audit.models import AuditEvent
from apps.core.errors import Problem
from apps.extensions.models import IntegrationSetting
from apps.extensions.settings_api import current_key

from .conftest import csrf, login, post

URL = "/api/v1/admin/integrations/rsv/"
KEY = "synthetic-rsv-test-key"


def save(client, key=KEY, tag=None):
    return client.put(
        URL,
        {"api_key": key},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
        HTTP_IF_MATCH=tag or client.get(URL)["ETag"],
    )


@pytest.mark.django_db
@pytest.mark.parametrize("who", [None, "user"])
def test_only_administrator(client, users, who):
    if who:
        login(client, who)
    assert client.get(URL).status_code == 403
    assert save(client, tag='"rsv-setting:0"').status_code == 403
    assert post(client, URL + "test/").status_code == 403
    assert not IntegrationSetting.objects.exists()


@pytest.mark.django_db
def test_encrypted_save_and_no_secret_read_or_audit(admin_client, settings):
    settings.RSV_API_KEY = "synthetic-environment-key"
    assert admin_client.get(URL).json()["source"] == "environment"
    result = save(admin_client)
    assert result.status_code == 200
    assert result.json()["source"] == "database"
    row = IntegrationSetting.objects.get(name="rsv")
    assert KEY not in row.encrypted_secret
    assert current_key() == KEY
    assert KEY not in str(result.json())
    assert KEY not in str(list(AuditEvent.objects.values()))
    assert save(admin_client, "replacement-test-key", tag='"rsv-setting:0"').status_code == 412
    assert current_key() == KEY


@pytest.mark.django_db
def test_csrf_precondition_and_validation(admin_client):
    assert admin_client.put(URL, {"api_key": KEY}, format="json").status_code == 403
    assert (
        admin_client.put(
            URL, {"api_key": KEY}, format="json", HTTP_X_CSRFTOKEN=csrf(admin_client)
        ).status_code
        == 428
    )
    assert save(admin_client, "key with spaces").status_code == 400
    assert not IntegrationSetting.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("status,found", [(1, True), (3, False)])
def test_probe_saved_key_without_creating_car(admin_client, status, found):
    from apps.vehicles.models import Vehicle

    save(admin_client)
    with patch(
        "apps.extensions.providers.fetch_json",
        return_value={"Status": status, "Data": {"test": "value"} if found else None},
    ) as fetch:
        result = post(admin_client, URL + "test/")
    assert result.status_code == 200
    assert result.json()["connected"] is True
    assert result.json()["vehicle_found"] is found
    assert fetch.call_args.args[1] == {"API_KEY": KEY}
    assert KEY not in str(result.json())
    assert not Vehicle.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("payload", [{"Status": 2}, [], {"error": "unknown"}])
def test_probe_rejects_unknown_response(admin_client, payload):
    save(admin_client)
    with patch("apps.extensions.providers.fetch_json", return_value=payload):
        assert post(admin_client, URL + "test/").status_code == 502
    assert not AuditEvent.objects.filter(action="integration.rsv_tested").exists()


@pytest.mark.django_db
def test_probe_error_and_missing_key(admin_client, settings):
    settings.RSV_API_KEY = ""
    assert post(admin_client, URL + "test/").status_code == 503
    save(admin_client)
    with patch(
        "apps.extensions.providers.fetch_json",
        side_effect=Problem("provider_authentication_failed", "Registr odmítl API klíč.", 502),
    ):
        result = post(admin_client, URL + "test/")
    assert result.status_code == 502
    assert not AuditEvent.objects.filter(action="integration.rsv_tested").exists()


@pytest.mark.django_db
def test_vin_lookup_uses_database_key(admin_client):
    from apps.extensions.providers import rsv

    save(admin_client)
    with patch("apps.extensions.providers.fetch_json", return_value={"Status": 3}) as fetch:
        with pytest.raises(Problem):
            rsv("TMBEFF654V7529422")
    assert fetch.call_args.args[1] == {"API_KEY": KEY}


@pytest.mark.django_db
def test_key_changed_during_probe(admin_client):
    from apps.extensions.settings_api import cipher

    save(admin_client)

    def changed(*args):
        IntegrationSetting.objects.filter(name="rsv").update(
            encrypted_secret=cipher().encrypt(b"changed-test-key").decode(), version=2
        )
        return {"Status": 1, "Data": {"test": True}}

    with patch("apps.extensions.providers.fetch_json", side_effect=changed):
        assert post(admin_client, URL + "test/").status_code == 412
    assert not AuditEvent.objects.filter(action="integration.rsv_tested").exists()
