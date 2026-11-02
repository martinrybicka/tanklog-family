import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from threading import Barrier
from unittest.mock import patch as mock_patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.utils import timezone
from openpyxl import load_workbook
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.refuelings.models import ReceiptAttachment, Refueling, RequestDeduplication
from apps.refuelings.quality import MESSAGES
from apps.refuelings.services import etag
from apps.vehicles.models import Vehicle, VehicleAccess

from .conftest import csrf, login, post

pytestmark = pytest.mark.django_db
BASE = "/api/v1/refuelings/"


@pytest.fixture
def vehicle(users):
    return Vehicle.objects.create(
        owner=users["user"],
        name="Rodinné auto",
        make="Škoda",
        model="Octavia",
        fuel_type="PETROL",
        initial_odometer_km=1000,
        tank_capacity_l="50",
    )


def data(vehicle, **changes):
    return {
        "vehicle_id": str(vehicle.pk),
        "date": "2026-01-10",
        "liters": "10.000",
        "unit_price_entered": "35.0000",
        "odometer_km": 1100,
        "confirmed_warning_codes": list(MESSAGES),
        **changes,
    }


def create(client, vehicle, key=None, **changes):
    return post(client, BASE, data(vehicle, **changes), HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))


def patch(client, url, body, tag):
    return client.patch(url, body, format="json", HTTP_X_CSRFTOKEN=csrf(client), HTTP_IF_MATCH=tag)


def png(name="synthetic.png", kind="PNG", content_type="image/png", animated=False, size=(20, 30)):
    stream = BytesIO()
    image = Image.new("RGB", size, "blue")
    options = {"save_all": True, "append_images": [Image.new("RGB", size, "red")]} if animated else {}
    image.save(stream, kind, **options)
    return SimpleUploadedFile(name, stream.getvalue(), content_type=content_type)


def test_amounts_idempotency_and_audit(admin_client, vehicle):
    key = uuid.uuid4()
    body = data(vehicle, liters="1.005", unit_price_entered="1.0000")
    first = post(admin_client, BASE, body, HTTP_IDEMPOTENCY_KEY=str(key))
    assert first.status_code == 201, first.json()
    assert first.json()["total_amount"] == "1.01"
    repeat = post(admin_client, BASE, body, HTTP_IDEMPOTENCY_KEY=str(key))
    assert repeat.status_code == 200 and repeat["Idempotency-Replayed"] == "true"
    assert repeat.json()["id"] == first.json()["id"]
    assert Refueling.objects.count() == 1
    assert AuditEvent.objects.filter(action="refueling.created").count() == 1
    conflict = post(admin_client, BASE, {**body, "liters": "2"}, HTTP_IDEMPOTENCY_KEY=str(key))
    assert conflict.status_code == 409
    RequestDeduplication.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    assert post(admin_client, BASE, body, HTTP_IDEMPOTENCY_KEY=str(key)).status_code == 409


def test_discount_explicit_amount_and_patch(admin_client, vehicle):
    created = create(admin_client, vehicle, total_amount="340.12")
    assert created.status_code == 201, created.json()
    url = BASE + created.json()["id"] + "/"
    response = patch(
        admin_client, url, {"liters": "20.000", "confirmed_warning_codes": list(MESSAGES)}, created["ETag"]
    )
    assert response.status_code == 200 and response.json()["total_amount"] == "340.12"
    assert response.json()["amount_source"] == "ENTERED"
    assert response.json()["effective_unit_price"] == "17.0060"
    assert patch(admin_client, url, {"note": "stará verze"}, created["ETag"]).status_code == 412
    assert patch(admin_client, url, {"vehicle_id": str(vehicle.pk)}, response["ETag"]).status_code == 400


@pytest.mark.parametrize(
    "changes",
    [
        {"liters": "0"},
        {"liters": "1.0001"},
        {"unit_price_entered": "1.00001"},
        {"total_amount": "1.001"},
        {"total_amount": "-1"},
        {"odometer_km": -1},
        {"odometer_km": 100000000},
        {"date": "2999-01-01"},
        {"created_by_id": str(uuid.uuid4())},
        {"paid_by_user_id": str(uuid.uuid4())},
        {"station_code": "OTHER"},
        {"station_custom_name": "nesprávně"},
        {"note": "a" * 2001},
    ],
)
def test_strict_validation(admin_client, vehicle, changes):
    response = create(admin_client, vehicle, **changes)
    assert response.status_code == 400, response.json()
    assert Refueling.objects.count() == 0
    assert RequestDeduplication.objects.count() == 0


def test_confirmations_missing_km_zero_and_no_key_consumption(admin_client, vehicle):
    key = uuid.uuid4()
    response = create(
        admin_client, vehicle, key, odometer_km=None, total_amount="0.00", confirmed_warning_codes=[]
    )
    assert response.status_code == 409
    assert {w["code"] for w in response.json()["error"]["warnings"]} == {
        "zero_amount",
        "missing_odometer",
        "amount_difference",
    }
    assert RequestDeduplication.objects.count() == 0
    accepted = create(admin_client, vehicle, key, odometer_km=None, total_amount="0.00")
    assert accepted.status_code == 201 and accepted.json()["odometer_km"] is None
    assert accepted.json()["total_amount"] == "0.00"
    invalid = create(admin_client, vehicle, unit_price_entered="0")
    assert invalid.status_code == 400
    assert post(admin_client, BASE, data(vehicle)).status_code == 400


@pytest.mark.parametrize(
    "role,own,archived,expected",
    [
        ("VIEWER", False, False, 403),
        ("CONTRIBUTOR", True, False, 200),
        ("CONTRIBUTOR", False, False, 403),
        ("CONTRIBUTOR", True, True, 403),
        ("OWNER", False, True, 200),
        ("ADMIN", False, True, 200),
    ],
)
def test_permissions(users, client, admin_client, vehicle, role, own, archived, expected):
    created = create(admin_client, vehicle)
    item = Refueling.objects.get()
    if role in ["VIEWER", "CONTRIBUTOR"]:
        VehicleAccess.objects.create(
            vehicle=vehicle, user=users["other"], role=role, granted_by=users["admin"]
        )
        who = "other"
    else:
        who = "user" if role == "OWNER" else "admin"
    if own:
        item.created_by = users[who]
        item.save()
    if archived:
        vehicle.status = "ARCHIVED"
        vehicle.archived_at = timezone.now()
        vehicle.save()
    login(client, who)
    response = patch(
        client,
        BASE + str(item.pk) + "/",
        {"note": "oprava", "confirmed_warning_codes": list(MESSAGES)},
        created["ETag"],
    )
    assert response.status_code == expected, response.json()
    item.refresh_from_db()
    deleted = client.delete(
        BASE + str(item.pk) + "/", HTTP_X_CSRFTOKEN=csrf(client), HTTP_IF_MATCH=etag(item)
    )
    assert deleted.status_code == (204 if role in ["OWNER", "ADMIN"] else 403)
    assert create(client, vehicle).status_code == (
        201 if role in ["CONTRIBUTOR", "OWNER", "ADMIN"] and not archived else 403
    )


def test_idor_revocation_export_and_payer_options(admin_client, users, client, vehicle):
    created = create(admin_client, vehicle)
    url = BASE + created.json()["id"] + "/"
    login(client, "other")
    for path in [
        url,
        url + "receipt/",
        BASE + f"?vehicle_id={vehicle.pk}",
        BASE + f"export/?vehicle_id={vehicle.pk}",
        f"/api/v1/vehicles/{vehicle.pk}/payer-options/",
    ]:
        assert client.get(path).status_code == 404
    assert create(client, vehicle).status_code == 404
    assert patch(client, url, {"note": "cizí"}, created["ETag"]).status_code == 404
    grant = VehicleAccess.objects.create(
        vehicle=vehicle, user=users["other"], role="CONTRIBUTOR", granted_by=users["admin"]
    )
    options = client.get(f"/api/v1/vehicles/{vehicle.pk}/payer-options/").json()["results"]
    assert all(set(option) == {"id", "display_name"} for option in options)
    assert client.get(url).status_code == 200
    grant.delete()
    assert client.get(url).status_code == 404
    assert client.get(BASE).json()["count"] == 0


def test_day_order_move_etag_and_history(admin_client, vehicle):
    first = create(admin_client, vehicle)
    second = create(admin_client, vehicle, odometer_km=1200)
    item = Refueling.objects.get(pk=first.json()["id"])
    day = "/api/v1/vehicles/" + str(vehicle.pk) + "/refueling-order/"
    current = admin_client.get(day + "?date=2026-01-10")
    ids = current.json()["ordered_ids"]
    assert ids == [first.json()["id"], second.json()["id"]]
    response = admin_client.put(
        day,
        {"date": "2026-01-10", "ordered_ids": list(reversed(ids))},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(admin_client),
        HTTP_IF_MATCH=current["ETag"],
    )
    assert response.status_code == 200
    assert patch(admin_client, BASE + str(item.pk) + "/", {"note": "stará"}, etag(item)).status_code == 412
    assert (
        admin_client.put(
            day,
            {"date": "2026-01-10", "ordered_ids": ids},
            format="json",
            HTTP_X_CSRFTOKEN=csrf(admin_client),
            HTTP_IF_MATCH=current["ETag"],
        ).status_code
        == 412
    )
    item.refresh_from_db()
    moved = patch(
        admin_client,
        BASE + str(item.pk) + "/",
        {"date": "2026-01-11", "confirmed_warning_codes": list(MESSAGES)},
        etag(item),
    )
    assert moved.status_code == 200
    assert Refueling.objects.get(pk=second.json()["id"]).day_sequence == 1
    assert moved.json()["day_sequence"] == 1


def test_filters_and_safe_typed_xlsx(admin_client, vehicle, settings):
    for index, prefix in enumerate(["=1+1", "+cmd", "-cmd", "@x", "\t=1", "\n=1", "  =2"]):
        assert (
            create(
                admin_client,
                vehicle,
                date=f"2026-01-{10 + index}",
                note=prefix,
                odometer_km=None,
                total_amount="320.15",
            ).status_code
            == 201
        )
    private = Vehicle.objects.create(
        owner=vehicle.owner, name="jiné", make="X", model="Y", fuel_type="DIESEL", initial_odometer_km=0
    )
    create(admin_client, private, station_code="SHELL")
    params = f"vehicle_id={vehicle.pk}&date_from=2026-01-10&date_to=2026-01-16&ordering=odometer_km"
    listed = admin_client.get(BASE + "?" + params).json()
    assert listed["count"] == 7
    response = admin_client.get(BASE + "export/?" + params)
    assert response.status_code == 200
    sheet = load_workbook(BytesIO(response.content)).active
    assert sheet.max_row == 8
    assert sheet["A2"].data_type == "d" and sheet["E2"].data_type == "n" and sheet["G2"].value == 320.15
    for row in sheet.iter_rows(min_row=2):
        assert row[11].data_type == "s"
        assert not any(cell.data_type == "f" for cell in row)
    assert admin_client.get(BASE + "?date_from=2026-02-01&date_to=2026-01-01").status_code == 400
    assert admin_client.get(BASE + "?station_code=SHELL").json()["count"] == 1
    assert admin_client.get(BASE + "?search=Rodinné").json()["count"] == 7
    assert admin_client.get(BASE + "?fuel_type=DIESEL").json()["count"] == 1
    empty = admin_client.get(BASE + "export/?search=nic-neexistuje")
    assert load_workbook(BytesIO(empty.content)).active.max_row == 1
    settings.REFUELING_EXPORT_LIMIT = 2
    assert admin_client.get(BASE + "export/?" + params).status_code == 400


def test_receipt_private_original_preview_replace_and_delete(admin_client, vehicle, client, users):
    created = create(admin_client, vehicle)
    url = BASE + created.json()["id"] + "/"
    upload = png("../../synthetic.png")
    original = upload.read()
    upload.seek(0)
    response = admin_client.post(
        url + "receipt/", {"file": upload}, HTTP_X_CSRFTOKEN=csrf(admin_client), HTTP_IF_MATCH=created["ETag"]
    )
    assert response.status_code == 201, response.json()
    assert bytes(ReceiptAttachment.objects.get().original_bytes) == original
    downloaded = admin_client.get(url + "receipt/")
    assert downloaded.content == original and downloaded["Cache-Control"].find("no-store") >= 0
    assert "attachment" in downloaded["Content-Disposition"] and ".." not in downloaded["Content-Disposition"]
    preview = admin_client.get(url + "receipt/?variant=preview")
    assert preview["Content-Type"] == "image/jpeg"
    assert Image.open(BytesIO(preview.content)).getexif() == {}
    client = APIClient(enforce_csrf_checks=True)
    login(client, "other")
    assert client.get(url + "receipt/").status_code == 404
    grant = VehicleAccess.objects.create(
        vehicle=vehicle, user=users["other"], role="VIEWER", granted_by=users["admin"]
    )
    assert client.get(url + "receipt/").status_code == 200
    assert (
        client.post(
            url + "receipt/", {"file": png()}, HTTP_X_CSRFTOKEN=csrf(client), HTTP_IF_MATCH=response["ETag"]
        ).status_code
        == 403
    )
    grant.delete()
    assert client.get(url + "receipt/").status_code == 404
    replaced = admin_client.put(
        url + "receipt/",
        {"file": png(kind="JPEG", content_type="image/jpeg")},
        HTTP_X_CSRFTOKEN=csrf(admin_client),
        HTTP_IF_MATCH=response["ETag"],
    )
    assert replaced.status_code == 200
    assert ReceiptAttachment.objects.get().version == 2
    assert (
        admin_client.delete(
            url + "receipt/", HTTP_X_CSRFTOKEN=csrf(admin_client), HTTP_IF_MATCH=replaced["ETag"]
        ).status_code
        == 204
    )
    assert ReceiptAttachment.objects.count() == 0
    assert Refueling.objects.count() == 1


@pytest.mark.parametrize("kind", ["broken", "mime", "gif", "animated", "large", "dimensions"])
def test_rejected_upload_preserves_record_and_previous_attachment(admin_client, vehicle, kind):
    created = create(admin_client, vehicle)
    url = BASE + created.json()["id"] + "/receipt/"
    if kind == "broken":
        upload = SimpleUploadedFile("bad.png", b"not an image", content_type="image/png")
    elif kind == "mime":
        upload = png(content_type="image/jpeg")
    elif kind == "gif":
        upload = png(kind="GIF", content_type="image/gif")
    elif kind == "animated":
        upload = png(animated=True)
    elif kind == "large":
        upload = SimpleUploadedFile("large.png", b"x" * (10 * 1024 * 1024 + 1), content_type="image/png")
    else:
        upload = png(size=(6000, 4001))
    result = admin_client.post(
        url, {"file": upload}, HTTP_X_CSRFTOKEN=csrf(admin_client), HTTP_IF_MATCH=created["ETag"]
    )
    assert result.status_code in [400, 413], result.json()
    assert Refueling.objects.count() == 1 and ReceiptAttachment.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_concurrent_retry_is_one_record(users, vehicle):
    barrier = Barrier(2)
    key = uuid.uuid4()

    def attempt(_):
        try:
            client = APIClient(enforce_csrf_checks=True)
            login(client, "admin")
            barrier.wait(timeout=10)
            return create(client, vehicle, key).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sorted(results) == [200, 201]
    assert Refueling.objects.count() == 1 and RequestDeduplication.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_edit_and_receipt_use_same_etag(users, vehicle):
    initial = APIClient(enforce_csrf_checks=True)
    login(initial, "admin")
    created = create(initial, vehicle)
    url = BASE + created.json()["id"] + "/"
    barrier = Barrier(2)

    def attempt(action):
        try:
            client = APIClient(enforce_csrf_checks=True)
            login(client, "admin")
            token = csrf(client)
            barrier.wait(timeout=10)
            if action == "edit":
                return patch(client, url, {"note": "současná oprava"}, created["ETag"]).status_code
            return client.post(
                url + "receipt/", {"file": png()}, HTTP_X_CSRFTOKEN=token, HTTP_IF_MATCH=created["ETag"]
            ).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["edit", "receipt"]))
    assert sorted(results) in [[200, 412], [201, 412]], results


def test_default_date_is_prague_and_confirmation_cannot_bypass_validation(admin_client, vehicle):
    from datetime import datetime
    from datetime import timezone as tz

    with mock_patch("django.utils.timezone.now", return_value=datetime(2026, 1, 10, 23, 30, tzinfo=tz.utc)):
        payload = data(vehicle)
        payload.pop("date")
        created = post(admin_client, BASE, payload, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        assert created.status_code == 201
        assert created.json()["date"] == "2026-01-11"
    response = create(admin_client, vehicle, liters="0", confirmed_warning_codes=list(MESSAGES))
    assert response.status_code == 400


def test_same_key_after_delete_or_revocation_never_recreates(admin_client, vehicle, users):
    client = APIClient(enforce_csrf_checks=True)
    VehicleAccess.objects.create(
        vehicle=vehicle, user=users["other"], role="CONTRIBUTOR", granted_by=users["admin"]
    )
    login(client, "other")
    key = uuid.uuid4()
    first = create(client, vehicle, key)
    assert first.status_code == 201
    VehicleAccess.objects.filter(vehicle=vehicle, user=users["other"]).delete()
    assert create(client, vehicle, key).status_code == 404
    item = Refueling.objects.get()
    assert (
        admin_client.delete(
            BASE + str(item.pk) + "/", HTTP_X_CSRFTOKEN=csrf(admin_client), HTTP_IF_MATCH=etag(item)
        ).status_code
        == 204
    )
    assert create(client, vehicle, key).status_code == 404
    assert Refueling.objects.count() == 0
    assert RequestDeduplication.objects.count() == 1


def test_upload_rate_and_failed_replacement_preserve_original(admin_client, vehicle, settings):
    created = create(admin_client, vehicle)
    url = BASE + created.json()["id"] + "/receipt/"
    good = admin_client.post(
        url, {"file": png()}, HTTP_X_CSRFTOKEN=csrf(admin_client), HTTP_IF_MATCH=created["ETag"]
    )
    assert good.status_code == 201
    saved = ReceiptAttachment.objects.get()
    invalid = admin_client.put(
        url,
        {"file": png(content_type="image/jpeg")},
        HTTP_X_CSRFTOKEN=csrf(admin_client),
        HTTP_IF_MATCH=good["ETag"],
    )
    assert invalid.status_code == 400
    assert ReceiptAttachment.objects.get().sha256 == saved.sha256
    assert Refueling.objects.get().version == good.json()["version"]
    settings.RECEIPT_UPLOADS_PER_MINUTE = 2
    limited = admin_client.put(
        url, {"file": png()}, HTTP_X_CSRFTOKEN=csrf(admin_client), HTTP_IF_MATCH=good["ETag"]
    )
    assert limited.status_code == 429
    assert limited["Retry-After"] == "60"


def test_export_is_whole_filtered_set_and_stable_nulls_last(admin_client, vehicle):
    from decimal import Decimal

    for i in range(30):
        Refueling.objects.create(
            vehicle=vehicle,
            date="2026-01-10",
            day_sequence=i + 1,
            liters=Decimal("10"),
            total_amount=Decimal("350"),
            amount_source="ENTERED",
            fuel_type="PETROL",
            odometer_km=None if i == 0 else 1100 + i,
            created_by=vehicle.owner,
            updated_by=vehicle.owner,
        )
    filtered_url = f"vehicle_id={vehicle.pk}&ordering=odometer_km"
    listed = admin_client.get(BASE + "?" + filtered_url).json()
    assert (
        listed["count"] == 30 and len(listed["results"]) == 25 and listed["results"][0]["odometer_km"] == 1101
    )
    workbook = load_workbook(BytesIO(admin_client.get(BASE + "export/?" + filtered_url).content))
    assert workbook.active.max_row == 31
    assert workbook.active["H31"].value is None
    assert [row[1].value for row in workbook.active.iter_rows(min_row=2)] == list(range(2, 31)) + [1]


def test_privatized_jpeg_preview_has_no_exif(admin_client, vehicle):
    created = create(admin_client, vehicle)
    buffer = BytesIO()
    exif = Image.Exif()
    exif[315] = "Syntetický autor"
    Image.new("RGB", (10, 10), "white").save(buffer, "JPEG", exif=exif)
    original = buffer.getvalue()
    response = admin_client.post(
        BASE + created.json()["id"] + "/receipt/",
        {"file": SimpleUploadedFile("synthetic.jpg", original, content_type="image/jpeg")},
        HTTP_X_CSRFTOKEN=csrf(admin_client),
        HTTP_IF_MATCH=created["ETag"],
    )
    assert response.status_code == 201
    receipt = ReceiptAttachment.objects.get()
    assert bytes(receipt.original_bytes) == original
    assert Image.open(BytesIO(bytes(receipt.preview_bytes))).getexif() == {}


@pytest.mark.django_db(transaction=True)
def test_concurrent_distinct_creates_keep_unique_day_positions(users, vehicle):
    VehicleAccess.objects.create(
        vehicle=vehicle, user=users["other"], role="CONTRIBUTOR", granted_by=users["admin"]
    )
    barrier = Barrier(2)

    def attempt(who):
        try:
            client = APIClient(enforce_csrf_checks=True)
            login(client, who)
            barrier.wait(timeout=10)
            return create(client, vehicle).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["admin", "other"]))
    assert sorted(results) == [201, 201]
    assert list(
        Refueling.objects.filter(vehicle=vehicle)
        .order_by("day_sequence")
        .values_list("day_sequence", flat=True)
    ) == [1, 2]


def test_future_consumption_fixtures_are_valid_history_inputs(admin_client, vehicle):
    import json
    from pathlib import Path

    scenarios = json.loads((Path(__file__).parent / "fixtures/refueling_scenarios.json").read_text())[
        "scenarios"
    ]
    for scenario in scenarios:
        car = Vehicle.objects.create(
            owner=vehicle.owner,
            name=scenario["id"],
            make="Fixture",
            model="Historie",
            fuel_type="PETROL",
            initial_odometer_km=scenario["initial_odometer_km"],
        )
        for record in scenario["records"]:
            assert create(admin_client, car, **record).status_code == 201
        assert list(
            Refueling.objects.filter(vehicle=car)
            .order_by("date", "day_sequence")
            .values_list("day_sequence", flat=True)
        ) == [r["day_sequence"] for r in scenario["records"]]


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_decimal_is_rejected(admin_client, vehicle, value):
    assert create(admin_client, vehicle, liters=value).status_code == 400
    assert Refueling.objects.count() == 0


def test_payer_identity_does_not_grant_access_and_historical_inactive_payer_is_preserved(
    admin_client, vehicle, users
):
    inaccessible = users["other"]
    assert create(admin_client, vehicle, paid_by_user_id=str(inaccessible.pk)).status_code == 400
    grant = VehicleAccess.objects.create(
        vehicle=vehicle, user=inaccessible, role="VIEWER", granted_by=users["admin"]
    )
    created = create(admin_client, vehicle, paid_by_user_id=str(inaccessible.pk))
    assert created.status_code == 201
    User.objects.filter(pk=inaccessible.pk).update(is_active=False)
    grant.delete()
    updated = patch(
        admin_client,
        BASE + created.json()["id"] + "/",
        {"note": "historická oprava", "paid_by_user_id": str(inaccessible.pk)},
        created["ETag"],
    )
    assert updated.status_code == 200
    assert updated.json()["paid_by_user_id"] == str(inaccessible.pk)


def test_vehicle_quality_change_invalidates_history_revision(admin_client, vehicle):
    create(admin_client, vehicle)
    from apps.vehicles.services import etag as vehicle_etag

    vehicle.refresh_from_db()
    before = vehicle.history_revision
    response = patch(
        admin_client, f"/api/v1/vehicles/{vehicle.pk}/", {"initial_odometer_km": 2000}, vehicle_etag(vehicle)
    )
    assert response.status_code == 200
    assert response.json()["history_revision"] == before + 1
    item = Refueling.objects.get()
    assert "odometer_below_initial" in {
        w["code"] for w in admin_client.get(BASE + str(item.pk) + "/").json()["quality_warnings"]
    }


def test_transparent_png_preview_is_flattened_on_white(admin_client, vehicle):
    created = create(admin_client, vehicle)
    buffer = BytesIO()
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(buffer, "PNG")
    response = admin_client.post(
        BASE + created.json()["id"] + "/receipt/",
        {"file": SimpleUploadedFile("transparent.png", buffer.getvalue(), content_type="image/png")},
        HTTP_X_CSRFTOKEN=csrf(admin_client),
        HTTP_IF_MATCH=created["ETag"],
    )
    assert response.status_code == 201
    preview = Image.open(BytesIO(bytes(ReceiptAttachment.objects.get().preview_bytes)))
    assert min(preview.getpixel((0, 0))) >= 250
