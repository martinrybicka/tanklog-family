import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.core.errors import Problem
from apps.extensions.models import ImportBatch, VehicleDataSnapshot, VehicleEvent
from apps.extensions.providers import fetch, map_rsv
from apps.extensions.rules import energy_totals, reminder_state
from apps.vehicles.models import Vehicle, VehicleAccess

from .conftest import csrf, login, post


def test_energy_totals_never_mix_units_or_round_via_float():
    assert energy_totals(
        [
            ("kWh", Decimal("12.345"), Decimal("100.10")),
            ("kg", Decimal("3.001"), Decimal("90.20")),
            ("kWh", Decimal("0.005"), Decimal("0.10")),
        ]
    ) == {
        "kWh": {"quantity": "12.350", "amount": "100.20"},
        "kg": {"quantity": "3.001", "amount": "90.20"},
    }


def test_reminder_date_km_and_unknown_reading():
    assert reminder_state(date(2026, 11, 3), date(2026, 11, 2), None, None, 30, 1000) == "OVERDUE"
    assert reminder_state(date(2026, 11, 3), None, 10000, 10000, 30, 1000) == "OVERDUE"
    assert reminder_state(date(2026, 11, 3), None, 10000, 9100, 30, 1000) == "SOON"
    assert reminder_state(date(2026, 11, 3), None, 10000, None, 30, 1000) == "UNKNOWN"


@pytest.fixture
def car(users):
    return Vehicle.objects.create(
        owner=users["user"],
        name="Test",
        make="Test",
        model="Model",
        fuel_type="PETROL",
        initial_odometer_km=0,
    )


def event_payload(**changes):
    return {
        "kind": "SERVICE",
        "title": "Výměna oleje",
        "date": "2026-01-02",
        "amount": "1234.56",
        "due_date": "2026-11-01",
        **changes,
    }


def create_event(client, car, **changes):
    return post(
        client,
        f"/api/v1/vehicles/{car.pk}/events/",
        event_payload(**changes),
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role,status",
    [("OWNER", 201), ("CONTRIBUTOR", 201), ("VIEWER", 403), ("NONE", 404)],
)
def test_events_roles(client, users, car, role, status):
    if role in ["CONTRIBUTOR", "VIEWER"]:
        VehicleAccess.objects.create(vehicle=car, user=users["other"], role=role, granted_by=users["admin"])
    login(client, "user" if role == "OWNER" else "other")
    assert create_event(client, car).status_code == status


@pytest.mark.django_db
def test_event_etag_retry_delete_and_no_resurrection(client, users, car):
    login(client, "user")
    url = f"/api/v1/vehicles/{car.pk}/events/"
    key = str(uuid.uuid4())
    first = post(client, url, event_payload(), HTTP_IDEMPOTENCY_KEY=key)
    assert first.status_code == 201
    second = post(client, url, event_payload(), HTTP_IDEMPOTENCY_KEY=key)
    assert second.json()["id"] == first.json()["id"] and VehicleEvent.objects.count() == 1
    detail = url + first.json()["id"] + "/"
    assert (
        client.put(
            detail,
            event_payload(title="Nová"),
            format="json",
            HTTP_X_CSRFTOKEN=csrf(client),
        ).status_code
        == 428
    )
    edited = client.put(
        detail,
        event_payload(title="Nová"),
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
        HTTP_IF_MATCH=first["ETag"],
    )
    assert edited.status_code == 200
    assert (
        client.delete(detail, HTTP_X_CSRFTOKEN=csrf(client), HTTP_IF_MATCH=first["ETag"]).status_code == 412
    )
    assert (
        client.delete(detail, HTTP_X_CSRFTOKEN=csrf(client), HTTP_IF_MATCH=edited["ETag"]).status_code == 204
    )
    assert post(client, url, event_payload(), HTTP_IDEMPOTENCY_KEY=key).status_code == 404


@pytest.mark.django_db
def test_contributor_cannot_edit_other_or_delete_own(client, users, car):
    VehicleAccess.objects.create(
        vehicle=car, user=users["other"], role="CONTRIBUTOR", granted_by=users["admin"]
    )
    login(client, "user")
    original = create_event(client, car)
    login(client, "other")
    base = f"/api/v1/vehicles/{car.pk}/events/"
    assert (
        client.put(
            base + original.json()["id"] + "/",
            event_payload(),
            format="json",
            HTTP_X_CSRFTOKEN=csrf(client),
            HTTP_IF_MATCH=original["ETag"],
        ).status_code
        == 403
    )
    own = create_event(client, car)
    assert own.status_code == 201
    assert (
        client.delete(
            base + own.json()["id"] + "/",
            HTTP_X_CSRFTOKEN=csrf(client),
            HTTP_IF_MATCH=own["ETag"],
        ).status_code
        == 403
    )
    from django.utils import timezone

    car.archived_at = timezone.now()
    car.status = "ARCHIVED"
    car.save()
    assert create_event(client, car).status_code == 403
    assert not client.get("/api/v1/reminders/").json()["results"]


@pytest.mark.django_db
def test_energy_precision_totals_and_private_reminders(client, users, car):
    login(client, "user")
    assert (
        create_event(
            client,
            car,
            kind="ENERGY",
            title="Nabíjení",
            quantity="12.345",
            unit="kWh",
            amount="100.10",
        ).status_code
        == 201
    )
    assert create_event(client, car, kind="ENERGY", quantity="2.3456", unit="kg").status_code == 400
    assert client.get(f"/api/v1/vehicles/{car.pk}/energy-totals/").json() == {
        "kWh": {"quantity": "12.345", "amount": "100.10"}
    }
    assert client.get("/api/v1/reminders/").json()["results"][0]["state"] == "OVERDUE"
    login(client, "other")
    assert client.get("/api/v1/reminders/").json()["count"] == 0
    assert client.get(f"/api/v1/vehicles/{car.pk}/energy-totals/").status_code == 404


@pytest.mark.django_db
def test_confirmed_csv_import_is_atomic_and_idempotent(client, users, car):
    from apps.refuelings.models import Refueling
    from apps.refuelings.quality import MESSAGES

    login(client, "user")
    url = f"/api/v1/vehicles/{car.pk}/imports/"
    preview = post(
        client,
        url,
        {
            "csv_text": "date;liters;total_amount;odometer_km\n2026-01-01;10,500;420,00;100\n2026-01-02;5,000;200,00;200"
        },
    )
    assert preview.status_code == 201 and not Refueling.objects.exists()
    batch = preview.json()
    assert not batch["errors"]
    result = post(
        client,
        f"/api/v1/imports/{batch['id']}/",
        {"confirmed": True, "confirmed_warning_codes": list(MESSAGES)},
    )
    assert result.status_code == 200 and Refueling.objects.count() == 2
    assert post(client, f"/api/v1/imports/{batch['id']}/", {"confirmed": True}).status_code == 200
    assert Refueling.objects.count() == 2
    login(client, "other")
    assert client.get(f"/api/v1/imports/{batch['id']}/").status_code == 404


@pytest.mark.django_db
def test_import_invalid_row_and_lost_access_never_write_history(client, users, car):
    from apps.refuelings.models import Refueling

    login(client, "user")
    url = f"/api/v1/vehicles/{car.pk}/imports/"
    response = post(
        client,
        url,
        {"csv_text": "date;liters;total_amount\n2026-01-01;10;400\n2026-01-02;invalid;200"},
    )
    batch = response.json()
    assert len(batch["errors"]) == 1
    assert post(client, f"/api/v1/imports/{batch['id']}/", {"confirmed": True}).status_code == 400
    assert not Refueling.objects.exists()
    # I při změně dat v náhledu se celá dávka při chybě vrátí.
    from apps.refuelings.quality import MESSAGES

    row = ImportBatch.objects.get(pk=batch["id"])
    row.errors = []
    row.rows[1] = {
        "date": "2026-01-02",
        "liters": "0",
        "total_amount": "0",
        "vehicle_id": str(car.pk),
    }
    row.save()
    assert (
        post(
            client,
            f"/api/v1/imports/{batch['id']}/",
            {"confirmed": True, "confirmed_warning_codes": list(MESSAGES)},
        ).status_code
        == 400
    )
    assert not Refueling.objects.exists()


def test_rsv_mapping_does_not_invent_year_power_or_consumption():
    vin = "TMB12345678901234"
    mapped = map_rsv(
        {
            "Status": 1,
            "Data": {
                "VIN": vin,
                "TovarniZnacka": "Test",
                "ObchodniOznaceni": "Model",
                "DatumPrvniRegistrace": "2020-01-01",
                "MotorMaxVykon": "110 / 5000",
                "SpotrebaNa100Km": "5 / 6 / 7",
            },
        },
        vin,
    )
    assert mapped == {"make": "Test", "model": "Model"}
    with pytest.raises(Problem):
        map_rsv({"Status": 1, "Data": {"VIN": "wrong"}}, vin)
    with pytest.raises(Problem):
        fetch("https://127.0.0.1/private")
    with pytest.raises(Problem):
        fetch("https://api.dataovozidlech.cz@evil.invalid/")


@pytest.mark.django_db
def test_vin_selective_confirmation_and_private_snapshot(client, users, car):
    vin = "TMB12345678901234"
    login(client, "user")
    raw = {
        "Status": 1,
        "Data": {"VIN": vin, "TovarniZnacka": "Test", "ObchodniOznaceni": "Novy"},
    }
    with patch(
        "apps.extensions.providers.rsv",
        return_value=(raw, {"make": "Test", "model": "Novy"}),
    ):
        response = post(client, "/api/v1/vehicle-lookups/", {"vin": vin, "vehicle_id": str(car.pk)})
    assert response.status_code == 201 and car.model == "Model"
    snapshot_id = response.json()["id"]
    url = f"/api/v1/vehicles/{car.pk}/"
    tag = client.get(url)["ETag"]
    update = client.patch(
        url,
        {
            "vin": vin,
            "make": "Test",
            "lookup_id": snapshot_id,
            "lookup_fields": ["make"],
        },
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
        HTTP_IF_MATCH=tag,
    )
    assert update.status_code == 200
    snapshot = VehicleDataSnapshot.objects.get(pk=snapshot_id)
    assert snapshot.confirmed and snapshot.applied_fields == ["make"]
    login(client, "other")
    with patch("apps.extensions.providers.rsv") as lookup:
        assert (
            post(
                client,
                "/api/v1/vehicle-lookups/",
                {"vin": vin, "vehicle_id": str(car.pk)},
            ).status_code
            == 404
        )
        lookup.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("fuel_type", ["CNG", "ELECTRIC"])
def test_cng_vehicle_cannot_create_liter_purchase(client, users, car, fuel_type):
    login(client, "user")
    url = f"/api/v1/vehicles/{car.pk}/"
    etag = client.get(url)["ETag"]
    result = client.patch(
        url,
        {"fuel_type": fuel_type},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
        HTTP_IF_MATCH=etag,
    )
    assert result.status_code == 200 and result.json()["consumption_mode"] == "UNSUPPORTED_UNIT"
    assert not result.json()["permissions"]["create_refueling"]
    assert (
        post(
            client,
            "/api/v1/refuelings/",
            {"vehicle_id": str(car.pk), "liters": "10", "total_amount": "100"},
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        ).status_code
        == 403
    )


def synthetic_image():
    import io

    from PIL import Image

    image = Image.new("RGB", (120, 80), "blue")
    stream = io.BytesIO()
    image.save(stream, "PNG")
    return stream.getvalue()


@pytest.mark.django_db
def test_photo_authorization_metadata_and_changed_match(client, users, car):
    from apps.extensions.integrations import photo_match
    from apps.extensions.models import VehicleImage

    login(client, "user")
    raw = synthetic_image()
    meta = {
        "author": "Syntetický autor",
        "license": "CC0 1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "source": "https://commons.wikimedia.org/wiki/File:Synthetic.png",
        "modified": "Náhled",
        "title": "Test",
    }
    image = VehicleImage.objects.create(
        vehicle=car,
        applicant=users["user"],
        original=raw,
        preview=raw,
        content_type="image/png",
        metadata=meta,
        match=photo_match(car),
    )
    source = f"/api/v1/vehicle-images/{image.pk}/"
    url = f"/api/v1/vehicles/{car.pk}/"
    etag = client.get(url)["ETag"]
    assert (
        post(
            client,
            url + "photo/",
            {"image_id": str(image.pk), "confirmed": False},
            HTTP_IF_MATCH=etag,
        ).status_code
        == 400
    )
    assert (
        post(
            client,
            url + "photo/",
            {"image_id": str(image.pk), "confirmed": True},
            HTTP_IF_MATCH=etag,
        ).status_code
        == 204
    )
    assert client.get(url).json()["photo"]["metadata"]["author"] == "Syntetický autor"
    VehicleAccess.objects.create(vehicle=car, user=users["other"], role="VIEWER", granted_by=users["admin"])
    login(client, "other")
    assert client.get(source).status_code == 200
    VehicleAccess.objects.filter(vehicle=car, user=users["other"]).delete()
    assert client.get(source).status_code == 404
    login(client, "user")
    car.make = "Changed"
    car.save()
    assert client.get(source).status_code == 404 and client.get(url).json()["photo"] is None


@pytest.mark.django_db
def test_ocr_stale_result_and_receipt_unchanged(client, users, car):
    import hashlib
    from datetime import date

    from apps.extensions.models import ReceiptExtraction
    from apps.refuelings.models import ReceiptAttachment, Refueling
    from apps.refuelings.services import etag

    login(client, "user")
    raw = synthetic_image()
    item = Refueling.objects.create(
        vehicle=car,
        date=date(2026, 1, 1),
        day_sequence=1,
        liters="10",
        total_amount="400",
        amount_source="ENTERED",
        fuel_type="PETROL",
        created_by=users["user"],
        updated_by=users["user"],
    )
    receipt = ReceiptAttachment.objects.create(
        refueling=item,
        original_bytes=raw,
        preview_bytes=raw,
        content_type="image/png",
        size_bytes=len(raw),
        width=120,
        height=80,
        sha256=hashlib.sha256(raw).hexdigest(),
        original_filename="synthetic.png",
        uploaded_by=users["user"],
    )
    with patch(
        "apps.extensions.ocr.engine",
        return_value=(
            "CELKEM 410,00",
            {"total_amount": {"value": "410.00", "confidence": "80"}},
        ),
    ):
        result = post(
            client,
            f"/api/v1/refuelings/{item.pk}/recognize/",
            {},
            HTTP_IF_MATCH=etag(item),
        )
    assert (
        result.status_code == 201
        and bytes(ReceiptAttachment.objects.get(pk=receipt.pk).original_bytes) == raw
    )
    record = ReceiptExtraction.objects.get(pk=result.json()["id"])
    receipt.version += 1
    receipt.save()
    query = client.get(f"/api/v1/refuelings/{item.pk}/extractions/{record.pk}/")
    assert query.json()["stale"]
    modified = client.patch(
        f"/api/v1/refuelings/{item.pk}/",
        {"extraction_id": str(record.pk), "total_amount": "410.00"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
        HTTP_IF_MATCH=etag(item),
    )
    assert modified.status_code == 409
    login(client, "other")
    assert client.get(f"/api/v1/refuelings/{item.pk}/extractions/{record.pk}/").status_code == 404


def test_ocr_parser_ambiguity_dates_and_decimal_strings():
    from apps.extensions.ocr import parse_tsv

    header = "level\tpage_num\tblock_num\tpar_num\tline_num\tconf\ttext\n"
    text = header + "5\t1\t1\t1\t1\t90\tCELKEM 420,00\n" + "5\t1\t1\t1\t2\t80\tMNOZSTVI 10,500 I\n"
    _, values = parse_tsv(text)
    assert values["total_amount"]["value"] == "420.00"
    assert values["liters"]["value"] == "10.500" and float(values["liters"]["confidence"]) <= 50
    _, values = parse_tsv(text + "5\t1\t1\t1\t3\t99\tCELKEM 999,00\n")
    assert "total_amount" not in values


@pytest.mark.django_db
def test_stale_import_history_or_revoked_access_is_rejected(client, users, car):
    login(client, "user")
    batch = post(
        client,
        f"/api/v1/vehicles/{car.pk}/imports/",
        {"csv_text": "date;liters;total_amount\n2026-01-01;10;400"},
    ).json()
    car.history_revision += 1
    car.save()
    assert post(client, f"/api/v1/imports/{batch['id']}/", {"confirmed": True}).status_code == 412
    car.owner = users["other"]
    car.save()
    assert post(client, f"/api/v1/imports/{batch['id']}/", {"confirmed": True}).status_code == 404


@pytest.mark.django_db
def test_global_integration_limit_is_sliding_not_fixed_window(client, users):
    from datetime import timedelta

    from django.utils import timezone

    from apps.extensions.models import IntegrationAttempt, IntegrationGate

    now = timezone.now()
    IntegrationGate.objects.create(name="rsv", window=now - timedelta(minutes=2), used=0)
    IntegrationAttempt.objects.bulk_create(
        [IntegrationAttempt(actor=users["other"], provider="rsv") for _ in range(20)]
    )
    login(client, "user")
    with patch("apps.extensions.providers.rsv") as call:
        response = post(client, "/api/v1/vehicle-lookups/", {"vin": "TMB12345678901234"})
        assert response.status_code == 429
        call.assert_not_called()


@pytest.mark.django_db
def test_event_csv_import_and_cross_device_saved_drafts(client, users, car):
    login(client, "user")
    data = {
        "kind": "EVENT",
        "csv_text": "kind;title;date;amount;quantity;unit\nENERGY;Test;2026-01-01;100.10;12.345;kWh",
    }
    response = post(client, f"/api/v1/vehicles/{car.pk}/imports/", data)
    assert response.status_code == 201
    batch = response.json()
    client.cookies.clear()
    login(client, "user")
    history = client.get(f"/api/v1/vehicles/{car.pk}/imports/").json()
    assert history["results"][0]["id"] == batch["id"]
    assert client.get(f"/api/v1/imports/{batch['id']}/").json()["csv_text"] == data["csv_text"]
    assert post(client, f"/api/v1/imports/{batch['id']}/", {"confirmed": True}).status_code == 200
    assert VehicleEvent.objects.get().quantity == Decimal("12.345")


def test_provider_bad_payload_and_body_limit_are_not_successes():
    from apps.extensions import providers

    with patch(
        "apps.extensions.providers.fetch",
        return_value="Pro Váš klíč dosažen maximální počet požadavků.".encode(),
    ):
        with pytest.raises(Problem) as limited:
            providers.fetch_json("https://api.dataovozidlech.cz/test")
        assert limited.value.status_code == 429
    with patch("apps.extensions.providers.fetch", return_value=b"<html>unavailable</html>"):
        with pytest.raises(Problem) as invalid:
            providers.fetch_json("https://api.dataovozidlech.cz/test")
        assert invalid.value.status_code == 502


def test_commons_license_whitelist_and_plain_author():
    from django.test import override_settings

    from apps.extensions.providers import commons

    image = {
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Test.jpg",
        "thumburl": "https://upload.wikimedia.org/test.jpg",
        "extmetadata": {
            "Artist": {"value": '<a href="/wiki/User:Example">Testovací autor</a>'},
            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
        },
    }
    missing = {
        **image,
        "extmetadata": {"LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"}},
    }
    restricted = {
        **image,
        "extmetadata": {
            **image["extmetadata"],
            "LicenseUrl": {"value": "https://example.invalid/restricted"},
        },
    }
    with (
        override_settings(COMMONS_USER_AGENT="SyntheticClosedTest/0.8 (test@example.invalid)"),
        patch(
            "apps.extensions.providers.fetch_json",
            return_value={
                "query": {
                    "pages": {
                        "1": {"imageinfo": [image]},
                        "2": {"imageinfo": [missing]},
                        "3": {"imageinfo": [restricted]},
                    }
                }
            },
        ),
    ):
        items = commons("Test", "Model")
    assert (
        len(items) == 1 and items[0]["author"] == "Testovací autor" and items[0]["license"] == "CC BY-SA 4.0"
    )


def test_image_validation_rejects_svg_corruption_and_oversize():
    from apps.extensions.integrations import image_payload

    for raw in [b"<svg>unsafe</svg>", b"not an image", b"x" * (5 * 1024**2 + 1)]:
        with pytest.raises(Problem):
            image_payload(raw)


@pytest.mark.django_db
def test_energy_quantity_is_nonnull_database_invariant(users, car):
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError), transaction.atomic():
        VehicleEvent.objects.create(
            vehicle=car,
            author=users["user"],
            kind="ENERGY",
            title="Chybné",
            date=date(2026, 1, 1),
            quantity=None,
            unit="kWh",
        )


@pytest.mark.django_db
def test_latest_ocr_result_is_accessible_without_client_state(client, users, car):
    from apps.extensions.models import ReceiptExtraction
    from apps.refuelings.models import Refueling

    login(client, "user")
    item = Refueling.objects.create(
        vehicle=car,
        date=date(2026, 1, 1),
        day_sequence=1,
        liters="10",
        total_amount="400",
        amount_source="ENTERED",
        fuel_type="PETROL",
        created_by=users["user"],
        updated_by=users["user"],
    )
    for text in ["první", "druhý"]:
        latest = ReceiptExtraction.objects.create(
            refueling=item,
            applicant=users["user"],
            receipt_hash="0" * 64,
            receipt_version=1,
            engine="test",
            raw_text=text,
            suggestions={},
        )
    response = client.get(f"/api/v1/refuelings/{item.pk}/recognize/")
    assert (
        response.status_code == 200 and response.json()["id"] == str(latest.pk) and response.json()["stale"]
    )


@pytest.mark.django_db
def test_vin_expiry_and_rights_recheck_after_provider(client, users, car):
    from datetime import timedelta

    from django.utils import timezone

    login(client, "user")
    vin = "TMB12345678901234"
    snapshot = VehicleDataSnapshot.objects.create(
        applicant=users["user"],
        vehicle=car,
        vin=vin,
        raw={"Status": 1, "Data": {"VIN": vin}},
        suggestions={"make": "New"},
    )
    VehicleDataSnapshot.objects.filter(pk=snapshot.pk).update(created_at=timezone.now() - timedelta(hours=25))
    url = f"/api/v1/vehicles/{car.pk}/"
    response = client.patch(
        url,
        {"vin": vin, "make": "New", "lookup_id": str(snapshot.pk), "lookup_fields": ["make"]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
        HTTP_IF_MATCH=client.get(url)["ETag"],
    )
    assert response.status_code == 409
    car.refresh_from_db()
    assert car.make == "Test" and car.vin is None

    def provider(_vin):
        car.owner = users["other"]
        car.save(update_fields=["owner"])
        return {"Status": 1, "Data": {"VIN": vin}}, {"make": "New"}

    with patch("apps.extensions.providers.rsv", side_effect=provider):
        response = post(client, "/api/v1/vehicle-lookups/", {"vin": vin, "vehicle_id": str(car.pk)})
    assert response.status_code == 404
    assert VehicleDataSnapshot.objects.count() == 1


@pytest.mark.django_db
def test_ocr_slots_are_bounded_and_expire():
    from datetime import timedelta

    from django.utils import timezone

    from apps.extensions.models import IntegrationGate
    from apps.extensions.ocr import acquire

    first, _ = acquire()
    second, _ = acquire()
    assert first != second
    with pytest.raises(Problem) as busy:
        acquire()
    assert busy.value.status_code == 429
    IntegrationGate.objects.filter(pk=first).update(window=timezone.now() - timedelta(seconds=1))
    assert acquire()[0] == first


def test_provider_timeout_redirect_private_dns_and_oversized_response():
    from unittest.mock import MagicMock

    address = [(2, 1, 6, "", ("8.8.8.8", 443))]
    with (
        patch("apps.extensions.providers.socket.getaddrinfo", return_value=address),
        patch("apps.extensions.providers.http.client.HTTPSConnection", side_effect=TimeoutError),
    ):
        with pytest.raises(Problem) as unavailable:
            fetch("https://api.dataovozidlech.cz/test")
        assert unavailable.value.status_code == 502
    private = [(2, 1, 6, "", ("127.0.0.1", 443))]
    with (
        patch("apps.extensions.providers.socket.getaddrinfo", return_value=private),
        patch("apps.extensions.providers.http.client.HTTPSConnection") as connection,
    ):
        with pytest.raises(Problem):
            fetch("https://api.dataovozidlech.cz/test")
        connection.assert_not_called()
    for status, content in [(302, b""), (200, b"12345")]:
        connection = MagicMock()
        connection.getresponse.return_value.status = status
        connection.getresponse.return_value.read.return_value = content
        with (
            patch("apps.extensions.providers.socket.getaddrinfo", return_value=address),
            patch("apps.extensions.providers.http.client.HTTPSConnection", return_value=connection),
        ):
            with pytest.raises(Problem):
                fetch("https://api.dataovozidlech.cz/test", maximum=4)
        connection.close.assert_called_once()


def test_ocr_timeout_kills_child_cleans_temp_and_omits_secrets(tmp_path, settings):
    import hashlib
    import json
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from apps.extensions.ocr import engine

    model = b"synthetic-model"
    (tmp_path / "eng.traineddata").write_bytes(model)
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"models": {"eng": {"sha256": hashlib.sha256(model).hexdigest()}}}))
    settings.OCR_DATA = str(tmp_path)
    settings.OCR_LOCK_FILE = str(lock)
    process = MagicMock()
    process.poll.return_value = None
    with (
        patch("apps.extensions.ocr.shutil.which", return_value="/synthetic/tesseract"),
        patch("apps.extensions.ocr.subprocess.run", return_value=SimpleNamespace(stdout="tesseract 5.5.4")),
        patch("apps.extensions.ocr.subprocess.Popen", return_value=process) as spawn,
        patch("apps.extensions.ocr.time.monotonic", side_effect=[0, 16]),
        patch.dict(
            "os.environ", {"RSV_API_KEY": "must-not-reach-child", "POSTGRES_PASSWORD": "must-not-reach-child"}
        ),
    ):
        with pytest.raises(Problem) as timeout:
            engine(synthetic_image())
    assert timeout.value.status_code == 504
    process.kill.assert_called_once()
    process.wait.assert_called_once()
    environment = spawn.call_args.kwargs["env"]
    assert "RSV_API_KEY" not in environment and "POSTGRES_PASSWORD" not in environment
    from pathlib import Path

    assert not Path(spawn.call_args.args[0][3]).exists()


@pytest.mark.django_db
def test_event_history_revision_invalidates_pending_event_import(client, users, car):
    login(client, "user")
    preview = post(
        client,
        f"/api/v1/vehicles/{car.pk}/imports/",
        {"kind": "EVENT", "csv_text": "kind;title;date\nSERVICE;Import;2026-01-01"},
    )
    assert preview.status_code == 201
    before = car.history_revision
    created = create_event(client, car)
    assert created.status_code == 201
    car.refresh_from_db()
    assert car.history_revision == before + 1
    result = post(client, f"/api/v1/imports/{preview.json()['id']}/", {"confirmed": True})
    assert result.status_code == 412
    assert VehicleEvent.objects.count() == 1


@pytest.mark.django_db
def test_event_can_change_from_energy_to_service(client, users, car):
    login(client, "user")
    energy = create_event(client, car, kind="ENERGY", quantity="1.234", unit="kWh")
    assert energy.status_code == 201
    result = client.put(
        f"/api/v1/vehicles/{car.pk}/events/{energy.json()['id']}/",
        event_payload(),
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
        HTTP_IF_MATCH=energy["ETag"],
    )
    assert result.status_code == 200
    assert result.json()["quantity"] is None and result.json()["unit"] == ""


@pytest.mark.django_db
def test_import_new_intra_batch_warnings_report_row_and_rollback(client, users, car):
    from apps.refuelings.models import Refueling

    login(client, "user")
    preview = post(
        client,
        f"/api/v1/vehicles/{car.pk}/imports/",
        {"kind": "FUEL", "csv_text": "date;liters;total_amount\n2026-01-01;1;0\n2026-01-01;1;0"},
    )
    assert preview.status_code == 201
    url = f"/api/v1/imports/{preview.json()['id']}/"
    confirmed = {warning["code"] for warning in preview.json()["warnings"]}
    first = post(client, url, {"confirmed": True, "confirmed_warning_codes": sorted(confirmed)})
    assert first.status_code == 409 and not Refueling.objects.exists()
    warnings = first.json()["error"]["warnings"]
    assert all(warning["row"] == 2 for warning in warnings)
    confirmed.update(warning["code"] for warning in warnings)
    second = post(client, url, {"confirmed": True, "confirmed_warning_codes": sorted(confirmed)})
    assert second.status_code == 200 and Refueling.objects.count() == 2


def test_malformed_provider_object_and_port_are_controlled_errors():
    with pytest.raises(Problem) as invalid:
        map_rsv([], "TMB12345678901234")
    assert invalid.value.status_code == 502
    with pytest.raises(Problem) as port:
        fetch("https://commons.wikimedia.org:invalid/test")
    assert port.value.status_code == 400
