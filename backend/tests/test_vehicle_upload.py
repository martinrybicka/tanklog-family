import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.extensions.models import VehicleImage
from apps.vehicles.models import Vehicle, VehicleAccess

from .conftest import csrf, login


@pytest.fixture
def car(users):
    return Vehicle.objects.create(
        owner=users["user"],
        name="Auto",
        make="Test",
        model="Model",
        fuel_type="PETROL",
        initial_odometer_km=0,
    )


def photo():
    output = io.BytesIO()
    exif = Image.Exif()
    exif[270] = "Soukromý popisek"
    Image.new("RGB", (60, 40), "blue").save(output, "JPEG", exif=exif)
    return SimpleUploadedFile("auto.jpg", output.getvalue(), content_type="image/jpeg")


def upload(client, car, tag=None, file=None):
    return client.post(
        f"/api/v1/vehicles/{car.pk}/photo-upload/",
        {"file": file or photo()},
        format="multipart",
        HTTP_X_CSRFTOKEN=csrf(client),
        HTTP_IF_MATCH=tag or client.get(f"/api/v1/vehicles/{car.pk}/")["ETag"],
    )


@pytest.mark.django_db
def test_upload_clean_private_photo_and_replace(client, users, car):
    login(client, "user")
    tag = client.get(f"/api/v1/vehicles/{car.pk}/")["ETag"]
    result = upload(client, car)
    assert result.status_code == 201
    image = VehicleImage.objects.get(vehicle=car, status="ACTIVE")
    assert image.metadata["kind"] == "upload"
    assert not Image.open(io.BytesIO(bytes(image.original))).getexif()
    source = result.json()["url"]
    assert client.get(source).status_code == 200
    assert upload(client, car, tag=tag).status_code == 412
    assert VehicleImage.objects.count() == 1
    assert upload(client, car).status_code == 201
    assert VehicleImage.objects.count() == 1
    assert client.get(source).status_code == 404
    login(client, "other")
    assert client.get(result.json()["url"]).status_code == 404
    assert (
        client.post(
            f"/api/v1/vehicles/{car.pk}/photo-upload/", {}, format="multipart", HTTP_X_CSRFTOKEN=csrf(client)
        ).status_code
        == 404
    )


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["VIEWER", "CONTRIBUTOR"])
def test_readers_cannot_upload(client, users, car, role):
    VehicleAccess.objects.create(vehicle=car, user=users["other"], role=role, granted_by=users["admin"])
    login(client, "other")
    assert upload(client, car).status_code == 403
    assert not VehicleImage.objects.exists()


@pytest.mark.django_db
def test_upload_validation_csrf_and_admin(client, users, car):
    login(client, "admin")
    url = f"/api/v1/vehicles/{car.pk}/photo-upload/"
    assert client.post(url, {"file": photo()}, format="multipart").status_code == 403
    assert (
        upload(
            client, car, file=SimpleUploadedFile("bad.jpg", b"not-image", content_type="image/jpeg")
        ).status_code
        == 400
    )
    assert upload(client, car).status_code == 201
    old = VehicleImage.objects.get().pk
    assert (
        client.post(
            url,
            {},
            format="multipart",
            HTTP_X_CSRFTOKEN=csrf(client),
            HTTP_IF_MATCH=client.get(f"/api/v1/vehicles/{car.pk}/")["ETag"],
        ).status_code
        == 400
    )
    assert VehicleImage.objects.get().pk == old
