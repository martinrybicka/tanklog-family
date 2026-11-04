import io
import uuid
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.family.models import FamilyPreference, ReceiptDraft
from apps.refuelings.models import ReceiptAttachment, Refueling
from apps.vehicles.models import Vehicle, VehicleAccess

from .conftest import csrf, login, post

pytestmark = pytest.mark.django_db


@pytest.fixture
def car(users):
    return Vehicle.objects.create(
        owner=users["user"],
        name="Rodinné auto",
        make="Test",
        model="Rodina",
        fuel_type="PETROL",
        initial_odometer_km=0,
    )


def upload(client, car, key=None):
    image = Image.new("RGB", (120, 80), "white")
    file = io.BytesIO()
    image.save(file, "PNG")
    return client.post(
        "/api/v1/family/receipts/",
        {
            "vehicle_id": str(car.pk),
            "file": SimpleUploadedFile("synteticka.png", file.getvalue(), "image/png"),
        },
        format="multipart",
        HTTP_X_CSRFTOKEN=csrf(client),
        HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()),
    )


def data(car, **changes):
    return {
        "vehicle_id": str(car.pk),
        "date": "2026-01-01",
        "liters": "12.345",
        "total_amount": "480.10",
        "odometer_km": 1000,
        **changes,
    }


def test_photo_first_draft_is_private_persistent_and_does_not_create_purchase(client, users, car):
    login(client, "user")
    key = uuid.uuid4()
    response = upload(client, car, key)
    assert response.status_code == 201
    assert not Refueling.objects.exists()
    retry = upload(client, car, key)
    assert retry.json()["id"] == response.json()["id"] and ReceiptDraft.objects.count() == 1
    path = f"/api/v1/family/receipts/{response.json()['id']}/"
    assert client.get(path + "image/").status_code == 200
    login(client, "other")
    assert client.get(path).status_code == 404
    assert client.get(path + "image/").status_code == 404
    assert client.get("/api/v1/family/receipts/").json()["results"] == []
    login(client, "user")
    assert client.get(path).status_code == 200
    assert client.get("/api/v1/family/receipts/").json()["results"][0]["id"] == response.json()["id"]


@pytest.mark.parametrize("role,status", [("VIEWER", 403), ("CONTRIBUTOR", 201), ("NONE", 404)])
def test_draft_upload_roles(client, users, car, role, status):
    if role != "NONE":
        VehicleAccess.objects.create(vehicle=car, user=users["other"], role=role, granted_by=users["admin"])
    login(client, "other")
    assert upload(client, car).status_code == status


def test_complete_receipt_atomically_and_retry_without_duplicate(client, users, car):
    login(client, "user")
    created = upload(client, car)
    path = f"/api/v1/family/receipts/{created.json()['id']}/complete/"
    assert post(client, path, data(car)).status_code == 428
    response = post(client, path, data(car), HTTP_IF_MATCH=created["ETag"])
    assert response.status_code == 201
    assert response.json()["total_amount"] == "480.10"
    assert response.json()["receipt"] is not None
    retry = post(client, path, data(car), HTTP_IF_MATCH=created["ETag"])
    assert retry.status_code == 201 and retry.json()["id"] == response.json()["id"]
    assert Refueling.objects.count() == ReceiptAttachment.objects.count() == 1
    draft = ReceiptDraft.objects.get()
    assert bytes(ReceiptAttachment.objects.get().original_bytes) == bytes(draft.original)
    assert (
        post(client, path, data(car, total_amount="490.10"), HTTP_IF_MATCH=created["ETag"]).status_code == 409
    )


def test_warnings_roll_back_whole_completion_and_can_be_confirmed(client, users, car):
    login(client, "user")
    draft = upload(client, car)
    path = f"/api/v1/family/receipts/{draft.json()['id']}/complete/"
    values = data(car, total_amount="0", odometer_km=None)
    response = post(client, path, values, HTTP_IF_MATCH=draft["ETag"])
    assert response.status_code == 409
    assert not Refueling.objects.exists() and not ReceiptAttachment.objects.exists()
    assert ReceiptDraft.objects.get().result_id is None
    codes = [w["code"] for w in response.json()["error"]["warnings"]]
    assert (
        post(
            client, path, {**values, "confirmed_warning_codes": codes}, HTTP_IF_MATCH=draft["ETag"]
        ).status_code
        == 201
    )


def test_recognition_preserves_photo_and_requires_current_tag(client, users, car):
    login(client, "user")
    draft = upload(client, car)
    path = f"/api/v1/family/receipts/{draft.json()['id']}/"
    with patch(
        "apps.family.services.ocr.engine",
        return_value=("CELKEM 480,10", {"total_amount": {"value": "480.10", "confidence": "90"}}),
    ):
        response = post(client, path + "recognize/", {}, HTTP_IF_MATCH=draft["ETag"])
    assert response.status_code == 200 and response["ETag"] != draft["ETag"]
    assert response.json()["suggestions"]["total_amount"]["value"] == "480.10"
    assert post(client, path + "complete/", data(car), HTTP_IF_MATCH=draft["ETag"]).status_code == 412
    assert not Refueling.objects.exists()


def test_revoke_access_during_recognition_does_not_save_suggestions(client, users, car):
    VehicleAccess.objects.create(
        vehicle=car, user=users["other"], role="CONTRIBUTOR", granted_by=users["admin"]
    )
    login(client, "other")
    draft = upload(client, car)

    def recognize(_raw):
        VehicleAccess.objects.filter(vehicle=car, user=users["other"]).delete()
        return "synteticky", {"total_amount": {"value": "100", "confidence": "90"}}

    with patch("apps.family.services.ocr.engine", side_effect=recognize):
        response = post(
            client,
            f"/api/v1/family/receipts/{draft.json()['id']}/recognize/",
            {},
            HTTP_IF_MATCH=draft["ETag"],
        )
    assert response.status_code == 404
    assert ReceiptDraft.objects.get().suggestions == {}


def test_admin_preselects_only_accessible_writable_vehicle_with_conflict_protection(client, users, car):
    login(client)
    path = f"/api/v1/family/admin/settings/{users['other'].pk}/"
    first = client.get(path)
    assert first.status_code == 200 and not FamilyPreference.objects.exists()

    def configure(tag):
        return client.put(
            path,
            {"default_vehicle_id": str(car.pk)},
            format="json",
            HTTP_X_CSRFTOKEN=csrf(client),
            HTTP_IF_MATCH=tag,
        )

    assert configure(first["ETag"]).status_code == 404
    grant = VehicleAccess.objects.create(
        vehicle=car, user=users["other"], role="VIEWER", granted_by=users["admin"]
    )
    assert configure(first["ETag"]).status_code == 403
    grant.role = "CONTRIBUTOR"
    grant.save()
    assert configure(first["ETag"]).status_code == 200
    assert configure(first["ETag"]).status_code == 412
    login(client, "other")
    assert client.get("/api/v1/family/settings/").json()["default_vehicle_id"] == str(car.pk)
    assert client.get(path).status_code == 403
    grant.delete()
    assert client.get("/api/v1/family/settings/").json()["default_vehicle_id"] is None


def test_draft_completion_cannot_target_different_vehicle_or_bypass_csrf(client, users, car):
    login(client, "user")
    draft = upload(client, car)
    path = f"/api/v1/family/receipts/{draft.json()['id']}/complete/"
    assert client.post(path, data(car), format="json", HTTP_IF_MATCH=draft["ETag"]).status_code == 403
    assert (
        post(client, path, data(car, vehicle_id=str(uuid.uuid4())), HTTP_IF_MATCH=draft["ETag"]).status_code
        == 400
    )
    assert not Refueling.objects.exists()
