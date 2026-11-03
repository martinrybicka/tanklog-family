from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connections
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.vehicles.models import Vehicle, VehicleAccess
from apps.vehicles.services import etag

from .conftest import PASSWORD, csrf, login, post

pytestmark = pytest.mark.django_db
DATA = {
    "name": "Rodinné auto",
    "make": "Škoda",
    "model": "Octavia",
    "fuel_type": "PETROL",
    "initial_odometer_km": 120000,
}


@pytest.fixture
def vehicle(users):
    return Vehicle.objects.create(owner=users["user"], **DATA)


def detail(vehicle):
    return f"/api/v1/vehicles/{vehicle.pk}/"


def access_url(vehicle):
    return f"/api/v1/admin/vehicles/{vehicle.pk}/access/"


def patch(client, url, data, tag=None):
    return client.patch(
        url,
        data,
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
        **({"HTTP_IF_MATCH": tag} if tag else {}),
    )


@pytest.mark.parametrize(
    "who,role,read,edit",
    [
        ("admin", None, 200, 200),
        ("user", None, 200, 200),
        ("other", "VIEWER", 200, 403),
        ("other", "CONTRIBUTOR", 200, 403),
        ("other", None, 404, 404),
    ],
)
def test_role_matrix(users, client, vehicle, who, role, read, edit):
    if role:
        VehicleAccess.objects.create(vehicle=vehicle, user=users[who], role=role, granted_by=users["admin"])
    assert login(client, who).status_code == 200
    assert client.get(detail(vehicle)).status_code == read
    assert patch(client, detail(vehicle), {"name": "Upravené"}, etag(vehicle)).status_code == edit
    expected_role = "ADMIN" if who == "admin" else "OWNER" if who == "user" else role
    if read == 200:
        assert client.get(detail(vehicle)).json()["effective_role"] == expected_role
    response = client.get("/api/v1/vehicles/").json()
    assert response["count"] == (1 if read == 200 else 0)


def test_creation_ownership_normalization_and_storage(users, client):
    login(client, "user")
    response = post(
        client,
        "/api/v1/vehicles/",
        {
            **DATA,
            "vin": " tmbjg7ne0j0123456 ",
            "registration_plate": " 1ab   2345 ",
            "standard_consumption_l_100km": "5.123",
            "power_kw": "110.25",
        },
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["owner_id"] == str(users["user"].pk)
    assert body["vin"] == "TMBJG7NE0J0123456"
    assert body["registration_plate"] == "1AB 2345"
    assert body["standard_consumption_l_100km"] == "5.123"
    assert body["power_kw"] == "110.25"
    assert body["effective_role"] == "OWNER"
    assert response["ETag"] == etag(Vehicle.objects.get(pk=body["id"]))
    client.cookies.clear()
    login(client, "user")
    assert client.get(f"/api/v1/vehicles/{body['id']}/").json()["vin"] == body["vin"]
    assert AuditEvent.objects.get(action="vehicle.created").vehicle_id == Vehicle.objects.get().pk


@pytest.mark.parametrize(
    "field,value",
    [
        ("initial_odometer_km", -1),
        ("initial_odometer_km", 100000000),
        ("initial_odometer_km", "1.5"),
        ("vin", "I" * 17),
        ("vin", "ABC"),
        ("power_kw", "1.234"),
        ("power_kw", "0"),
        ("tank_capacity_l", "-1"),
        ("standard_consumption_l_100km", "0"),
        ("standard_consumption_l_100km", "1.0001"),
        ("manufacture_year", 1885),
        ("manufacture_year", 9999),
        ("name", " "),
        ("fuel_type", "UNSUPPORTED_FUEL"),
        ("owner_id", "00000000-0000-0000-0000-000000000001"),
        ("status", "ARCHIVED"),
        ("version", 100),
        ("history_revision", 500),
    ],
)
def test_validation_and_mass_assignment(admin_client, field, value):
    response = post(admin_client, "/api/v1/vehicles/", {**DATA, field: value})
    assert response.status_code == 400, response.json()
    assert Vehicle.objects.count() == 0


def test_vin_conflict_is_generic_and_blank_is_not_unique(users, client, vehicle):
    vehicle.vin = "TMBJG7NE0J0123456"
    vehicle.save()
    login(client, "other")
    response = post(client, "/api/v1/vehicles/", {**DATA, "vin": vehicle.vin.lower()})
    assert response.status_code == 400
    assert str(vehicle.pk) not in str(response.json())
    assert "user" not in str(response.json())
    for vin in ["", None, ""]:
        assert post(client, "/api/v1/vehicles/", {**DATA, "vin": vin}).status_code == 201


def test_etags_archive_restore_and_no_delete(users, client, vehicle):
    login(client, "user")
    tag = etag(vehicle)
    assert patch(client, detail(vehicle), {"name": "Nové"}).status_code == 428
    assert patch(client, detail(vehicle), {"name": "Nové"}, '"wrong"').status_code == 412
    response = post(client, detail(vehicle) + "archive/", HTTP_IF_MATCH=tag)
    assert response.status_code == 200
    assert response.json()["archived_at"]
    assert client.get("/api/v1/vehicles/").json()["count"] == 0
    assert client.get("/api/v1/vehicles/?status=archived").json()["count"] == 1
    assert client.get("/api/v1/vehicles/?status=all").json()["count"] == 1
    assert post(client, detail(vehicle) + "restore/", HTTP_IF_MATCH=tag).status_code == 412
    restored = post(client, detail(vehicle) + "restore/", HTTP_IF_MATCH=response["ETag"])
    assert restored.status_code == 200
    assert restored.json()["archived_at"] is None
    assert Vehicle.objects.count() == 1
    assert client.delete(detail(vehicle), HTTP_X_CSRFTOKEN=csrf(client)).status_code == 405
    assert (
        patch(
            client,
            detail(vehicle),
            {"owner_id": str(users["other"].pk)},
            restored["ETag"],
        ).status_code
        == 400
    )
    assert client.get("/api/v1/vehicles/?status=invalid").status_code == 400


def test_sharing_and_revocation(admin_client, users, vehicle):
    response = post(
        admin_client,
        access_url(vehicle),
        {"user_id": str(users["other"].pk), "role": "VIEWER"},
    )
    assert response.status_code == 201
    grant_id = response.json()["id"]
    url = f"/api/v1/admin/vehicle-access/{grant_id}/"
    assert (
        post(
            admin_client,
            access_url(vehicle),
            {"user_id": str(users["other"].pk), "role": "CONTRIBUTOR"},
        ).status_code
        == 409
    )
    assert (
        post(
            admin_client,
            access_url(vehicle),
            {"user_id": str(users["user"].pk), "role": "VIEWER"},
        ).status_code
        == 409
    )
    other = APIClient(enforce_csrf_checks=True)
    login(other, "other")
    assert other.get(detail(vehicle)).json()["effective_role"] == "VIEWER"
    changed = patch(admin_client, url, {"role": "CONTRIBUTOR"}, response["ETag"])
    assert changed.status_code == 200
    assert patch(admin_client, url, {"role": "VIEWER"}, response["ETag"]).status_code == 412
    assert patch(admin_client, url, {"user_id": str(users["user"].pk)}, changed["ETag"]).status_code == 400
    assert other.get(detail(vehicle)).json()["effective_role"] == "CONTRIBUTOR"
    assert (
        admin_client.delete(
            url, HTTP_X_CSRFTOKEN=csrf(admin_client), HTTP_IF_MATCH=changed["ETag"]
        ).status_code
        == 204
    )
    assert other.get(detail(vehicle)).status_code == 404
    assert Vehicle.objects.count() == 1
    assert AuditEvent.objects.filter(vehicle_id=vehicle.pk).count() == 3


@pytest.mark.parametrize("previous_role", [None, "VIEWER", "CONTRIBUTOR"])
def test_atomic_transfer_explicit_previous_access(admin_client, users, vehicle, previous_role):
    VehicleAccess.objects.create(
        vehicle=vehicle, user=users["other"], role="VIEWER", granted_by=users["admin"]
    )
    data = {"new_owner_id": str(users["other"].pk), "current_password": PASSWORD}
    if previous_role:
        data["previous_owner_role"] = previous_role
    response = post(
        admin_client,
        f"/api/v1/admin/vehicles/{vehicle.pk}/transfer-owner/",
        data,
        HTTP_IF_MATCH=etag(vehicle),
    )
    assert response.status_code == 200
    vehicle.refresh_from_db()
    assert vehicle.owner_id == users["other"].pk
    assert not VehicleAccess.objects.filter(vehicle=vehicle, user=users["other"]).exists()
    old = VehicleAccess.objects.filter(vehicle=vehicle, user=users["user"]).first()
    assert (old.role if old else None) == previous_role
    client = APIClient(enforce_csrf_checks=True)
    login(client, "user")
    assert client.get(detail(vehicle)).status_code == (200 if previous_role else 404)
    assert patch(client, detail(vehicle), {"name": "Pokus"}, etag(vehicle)).status_code == (
        403 if previous_role else 404
    )
    assert (
        AuditEvent.objects.get(action="vehicle.owner_transferred").changes["previous_owner_role"]
        == previous_role
    )


def test_inactive_targets_and_transfer_reauth(admin_client, users, vehicle):
    User.objects.filter(pk=users["other"].pk).update(is_active=False)
    assert (
        post(
            admin_client,
            access_url(vehicle),
            {"user_id": str(users["other"].pk), "role": "VIEWER"},
        ).status_code
        == 400
    )
    url = f"/api/v1/admin/vehicles/{vehicle.pk}/transfer-owner/"
    data = {"new_owner_id": str(users["other"].pk), "current_password": "incorrect"}
    assert post(admin_client, url, data, HTTP_IF_MATCH=etag(vehicle)).status_code == 403
    data["current_password"] = PASSWORD
    assert post(admin_client, url, data, HTTP_IF_MATCH=etag(vehicle)).status_code == 400
    vehicle.refresh_from_db()
    assert vehicle.owner_id == users["user"].pk
    assert not AuditEvent.objects.filter(action="vehicle.owner_transferred").exists()


def test_private_admin_endpoints_and_csrf(users, client, vehicle):
    assert client.get(detail(vehicle)).status_code == 403
    login(client, "user")
    for url in [access_url(vehicle), "/api/v1/admin/vehicles/", "/api/v1/admin/users/"]:
        assert client.get(url).status_code == 403
    assert (
        post(
            client,
            access_url(vehicle),
            {"user_id": str(users["other"].pk), "role": "VIEWER"},
        ).status_code
        == 403
    )
    assert (
        post(
            client,
            f"/api/v1/admin/vehicles/{vehicle.pk}/transfer-owner/",
            {"new_owner_id": str(users["other"].pk), "current_password": PASSWORD},
            HTTP_IF_MATCH=etag(vehicle),
        ).status_code
        == 403
    )
    assert client.post("/api/v1/vehicles/", DATA, format="json").status_code == 403
    User.objects.filter(pk=users["user"].pk).update(is_active=False, auth_epoch=2)
    assert client.get(detail(vehicle)).status_code == 403


def test_restricted_session_cannot_access_vehicles(users, client):
    from apps.accounts.services import set_temporary_password

    user = users["admin"]
    password = set_temporary_password(user)
    user.save()
    assert login(client, "admin", password).status_code == 200
    assert client.get("/api/v1/vehicles/").status_code == 403
    assert client.get("/api/v1/admin/vehicles/").status_code == 403
    assert post(client, "/api/v1/vehicles/", DATA).status_code == 403


@pytest.mark.django_db(transaction=True)
def test_transfer_and_sharing_serialize(users, vehicle):
    barrier = Barrier(2)

    def attempt(action):
        try:
            client = APIClient(enforce_csrf_checks=True)
            login(client, "admin")
            tag = etag(vehicle)
            barrier.wait(timeout=10)
            if action == "transfer":
                return post(
                    client,
                    f"/api/v1/admin/vehicles/{vehicle.pk}/transfer-owner/",
                    {
                        "new_owner_id": str(users["other"].pk),
                        "current_password": PASSWORD,
                    },
                    HTTP_IF_MATCH=tag,
                ).status_code
            return post(
                client,
                access_url(vehicle),
                {"user_id": str(users["other"].pk), "role": "VIEWER"},
            ).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["transfer", "share"]))
    assert results in [[200, 409], [412, 201]], results
    vehicle.refresh_from_db()
    assert not VehicleAccess.objects.filter(vehicle=vehicle, user=vehicle.owner).exists()
    assert Vehicle.objects.count() == 1


@pytest.mark.parametrize("role", ["VIEWER", "CONTRIBUTOR"])
def test_shared_user_cannot_archive_restore_or_manage_grants(users, client, vehicle, role):
    grant = VehicleAccess.objects.create(
        vehicle=vehicle, user=users["other"], role=role, granted_by=users["admin"]
    )
    login(client, "other")
    for action in ["archive", "restore"]:
        assert post(client, detail(vehicle) + action + "/", HTTP_IF_MATCH=etag(vehicle)).status_code == 403
    url = f"/api/v1/admin/vehicle-access/{grant.pk}/"
    assert client.get(url).status_code == 403
    assert patch(client, url, {"role": "VIEWER"}, etag(grant)).status_code == 403
    assert client.delete(url, HTTP_X_CSRFTOKEN=csrf(client), HTTP_IF_MATCH=etag(grant)).status_code == 403
    assert client.get("/api/v1/vehicles/?status=all").json()["count"] == 1


def test_grant_etag_missing_and_deactivated_owner_can_be_transferred(admin_client, users, vehicle):
    grant = VehicleAccess.objects.create(
        vehicle=vehicle, user=users["other"], role="VIEWER", granted_by=users["admin"]
    )
    url = f"/api/v1/admin/vehicle-access/{grant.pk}/"
    assert patch(admin_client, url, {"role": "CONTRIBUTOR"}).status_code == 428
    assert admin_client.delete(url, HTTP_X_CSRFTOKEN=csrf(admin_client)).status_code == 428
    User.objects.filter(pk=users["user"].pk).update(is_active=False)
    response = post(
        admin_client,
        f"/api/v1/admin/vehicles/{vehicle.pk}/transfer-owner/",
        {"new_owner_id": str(users["other"].pk), "current_password": PASSWORD},
        HTTP_IF_MATCH=etag(vehicle),
    )
    assert response.status_code == 200
    assert not VehicleAccess.objects.filter(vehicle=vehicle).exists()
    assert admin_client.get("/api/v1/admin/vehicles/").json()["count"] == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_duplicate_grants_create_one_row(users, vehicle, password_hash):
    second = User.objects.create(username="admin2", password=password_hash, system_role="ADMIN")
    barrier = Barrier(2)

    def attempt(username):
        try:
            client = APIClient(enforce_csrf_checks=True)
            login(client, username)
            barrier.wait(timeout=10)
            return post(
                client,
                access_url(vehicle),
                {"user_id": str(users["other"].pk), "role": "VIEWER"},
            ).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["admin", second.username]))
    assert sorted(results) == [201, 409]
    assert VehicleAccess.objects.filter(vehicle=vehicle).count() == 1
    assert AuditEvent.objects.filter(action="vehicle.access_created").count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_owner_update_and_transfer_cannot_overwrite_new_ownership(users, vehicle):
    barrier = Barrier(2)

    def attempt(who):
        try:
            client = APIClient(enforce_csrf_checks=True)
            login(client, who)
            tag = etag(vehicle)
            barrier.wait(timeout=10)
            if who == "admin":
                return post(
                    client,
                    f"/api/v1/admin/vehicles/{vehicle.pk}/transfer-owner/",
                    {
                        "new_owner_id": str(users["other"].pk),
                        "current_password": PASSWORD,
                    },
                    HTTP_IF_MATCH=tag,
                ).status_code
            return patch(client, detail(vehicle), {"name": "Nové jméno"}, tag).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        transfer, update = list(pool.map(attempt, ["admin", "user"]))
    assert (transfer, update) in [(200, 404), (412, 200)]
    vehicle.refresh_from_db()
    assert vehicle.owner_id == (users["other"].pk if transfer == 200 else users["user"].pk)
