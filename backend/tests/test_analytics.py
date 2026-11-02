from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from types import SimpleNamespace

import pytest
from django.db import connections, transaction

from apps.accounts.models import User
from apps.analytics import services
from apps.refuelings.models import Refueling
from apps.vehicles.models import Vehicle, VehicleAccess

from .conftest import csrf, login

pytestmark = pytest.mark.django_db(transaction=True)
BASE = "/api/v1/dashboard/"
PARAMS = "period=custom&date_from=2026-02-01&date_to=2026-02-28"


@pytest.fixture
def car(users):
    return Vehicle.objects.create(
        owner=users["user"],
        name="Rodinné auto",
        make="Škoda",
        model="Octavia",
        fuel_type="PETROL",
        initial_odometer_km=0,
        standard_consumption_l_100km="6",
        standard_methodology="WLTP",
        standard_source="Výrobce",
    )


@pytest.fixture
def history(car, users):
    rows = []
    for day, km, liters, full in [
        ("2026-01-31", 10000, "50", True),
        ("2026-02-01", 10300, "20", False),
        ("2026-02-05", 10600, "25", True),
    ]:
        rows.append(
            Refueling.objects.create(
                vehicle=car,
                date=day,
                day_sequence=1,
                liters=liters,
                total_amount=Decimal(liters) * 40,
                amount_source="ENTERED",
                fuel_type=car.fuel_type,
                odometer_km=km,
                is_full_tank=full,
                created_by=users["user"],
                updated_by=users["user"],
            )
        )
    return rows


def test_dashboard_and_interval_detail_consistent(admin_client, car, history):
    response = admin_client.get(BASE + f"?{PARAMS}&vehicle_id={car.pk}")
    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["purchases"] == {
        "amount": "1800.00",
        "liters": "45.000",
        "count": 2,
        "realized_unit_price": "40.000000",
    }
    assert data["consumption_l_100km"] == "7.500000"
    assert data["coverage"]["distance_km"] == 600 and data["coverage"]["start_date"] == "2026-01-31"
    assert data["comparison"]["difference_percent"] == "25.000000"
    assert data["comparison"]["methodology"] == "WLTP"
    interval = data["charts"]["consumption"][0]
    assert interval["crosses_period_start"] and interval["liters"] == "45.000"
    detail = admin_client.get(
        f"/api/v1/vehicles/{car.pk}/consumption-intervals/detail/?{PARAMS}&start_id={history[0].pk}&end_id={history[-1].pk}"
    )
    assert detail.status_code == 200
    records = detail.json()["records"]
    assert [r["used_for_totals"] for r in records] == [False, True, True]
    assert records[0]["date"] == "2026-01-31"
    assert response["Cache-Control"] == "private, no-store"
    assert (
        admin_client.get(f"/api/v1/vehicles/{car.pk}/statistics/?{PARAMS}").json()["purchases"]
        == data["purchases"]
    )


def test_empty_null_and_no_generic_comparison(admin_client, car):
    data = admin_client.get(BASE + f"?{PARAMS}").json()
    assert data["purchases"]["amount"] == "0.00" and data["purchases"]["count"] == 0
    assert data["purchases"]["realized_unit_price"] is None and data["consumption_l_100km"] is None
    assert data["comparison"] is None and data["coverage"]["vehicles"][0]["status"] == "INSUFFICIENT_DATA"
    assert all(point["unit_price"] is None for point in data["charts"]["purchases"])


@pytest.mark.parametrize(
    "query",
    [
        "period=invalid",
        "period=custom",
        "period=custom&date_from=2026-02-02&date_to=2026-02-01",
        "period=custom&date_from=2026-02-01&date_to=2026-02-02&anchor_date=2026-02-01",
        "date_from=2026-02-01",
        "group_by=hour",
        "unknown=x",
        "period=custom&date_from=1900-01-01&date_to=2026-01-01&group_by=day",
    ],
)
def test_period_validation(admin_client, query):
    response = admin_client.get(BASE + "?" + query)
    assert response.status_code == 400, response.json()


def test_roles_idor_and_redundant_grants_do_not_multiply(users, client, car, history):
    login(client, "other")
    assert client.get(BASE + f"?{PARAMS}").json()["purchases"]["count"] == 0
    for endpoint in [
        "statistics/",
        "consumption-intervals/",
        f"consumption-intervals/detail/?start_id={history[0].pk}&end_id={history[-1].pk}&",
    ]:
        url = f"/api/v1/vehicles/{car.pk}/{endpoint}"
        url += PARAMS if "?" in endpoint else "?" + PARAMS
        assert client.get(url).status_code == 404
    grant = VehicleAccess.objects.create(
        vehicle=car, user=users["other"], role="VIEWER", granted_by=users["admin"]
    )
    assert client.get(BASE + f"?{PARAMS}").json()["purchases"]["count"] == 2
    grant.delete()
    assert client.get(BASE + f"?{PARAMS}&vehicle_id={car.pk}").status_code == 404
    login(client, "user")
    VehicleAccess.objects.create(
        vehicle=car, user=users["user"], role="CONTRIBUTOR", granted_by=users["admin"]
    )
    assert client.get(BASE + f"?{PARAMS}").json()["purchases"]["count"] == 2
    User.objects.filter(pk=users["user"].pk).update(is_active=False)
    assert client.get(BASE).status_code == 403


def test_limited_session_and_unauthenticated_cannot_read(users, client, car):
    assert client.get(BASE).status_code == 403
    from apps.accounts.services import set_temporary_password

    user = users["admin"]
    password = set_temporary_password(user)
    user.save()
    assert login(client, "admin", password).status_code == 200
    assert client.get(BASE).status_code == 403


def test_archived_history_and_multiple_fuels(admin_client, car, history, users):
    car.status = "ARCHIVED"
    car.archived_at = "2026-01-01T00:00:00Z"
    car.save()
    other = Vehicle.objects.create(
        owner=users["user"], name="Nafta", make="X", model="Y", fuel_type="DIESEL", initial_odometer_km=0
    )
    for index, (km, liters) in enumerate([(0, 50), (500, 35)]):
        Refueling.objects.create(
            vehicle=other,
            date=date(2026, 2, 1 + index),
            day_sequence=1,
            liters=liters,
            total_amount=liters * 40,
            amount_source="ENTERED",
            fuel_type="DIESEL",
            odometer_km=km,
            is_full_tank=True,
            created_by=users["user"],
            updated_by=users["user"],
        )
    data = admin_client.get(BASE + "?" + PARAMS).json()
    assert data["consumption_l_100km"] is None
    assert {g["fuel_type"]: g["consumption_l_100km"] for g in data["consumption_by_fuel"]} == {
        "PETROL": "7.500000",
        "DIESEL": "7.000000",
    }
    assert data["coverage"]["valid_intervals"] == 2


def test_period_boundaries_graphs_and_purchase_weights(admin_client, car, history):
    day = admin_client.get(BASE + f"?period=day&anchor_date=2026-02-01&vehicle_id={car.pk}").json()
    assert day["purchases"]["liters"] == "20.000" and day["consumption_l_100km"] is None
    week = admin_client.get(BASE + "?period=week&anchor_date=2026-01-01").json()["period"]
    assert week["date_from"] == "2025-12-29" and week["date_to"] == "2026-01-04"
    points = admin_client.get(BASE + f"?{PARAMS}&group_by=week").json()["charts"]["purchases"]
    assert points[0]["date"] == "2026-01-26" and points[0]["liters"] == "20.000"
    assert points[1]["liters"] == "25.000"


def test_backdated_edit_delete_and_order_recompute(admin_client, car, history):
    url = BASE + f"?{PARAMS}&vehicle_id={car.pk}"
    assert admin_client.get(url).json()["consumption_l_100km"] == "7.500000"
    item = history[1]
    detail = admin_client.get(f"/api/v1/refuelings/{item.pk}/")
    edited = admin_client.patch(
        f"/api/v1/refuelings/{item.pk}/",
        {"liters": "15", "confirmed_warning_codes": ["amount_difference"]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(admin_client),
        HTTP_IF_MATCH=detail["ETag"],
    )
    assert edited.status_code == 200, edited.json()
    assert admin_client.get(url).json()["consumption_l_100km"] == "6.666667"
    assert (
        admin_client.delete(
            f"/api/v1/refuelings/{item.pk}/",
            HTTP_X_CSRFTOKEN=csrf(admin_client),
            HTTP_IF_MATCH=edited["ETag"],
        ).status_code
        == 204
    )
    assert admin_client.get(url).json()["consumption_l_100km"] == "4.166667"
    Refueling.objects.create(
        vehicle=car,
        date="2026-02-03",
        day_sequence=1,
        liters="5",
        total_amount="200",
        amount_source="ENTERED",
        fuel_type="PETROL",
        odometer_km=10400,
        is_full_tank=False,
        created_by=car.owner,
        updated_by=car.owner,
    )
    assert admin_client.get(url).json()["consumption_l_100km"] == "5.000000"


def test_invalid_interval_has_null_chart_and_changed_detail_is_404(admin_client, car, history):
    history[1].break_before = True
    history[1].save()
    data = admin_client.get(BASE + f"?{PARAMS}&vehicle_id={car.pk}").json()
    assert data["charts"]["consumption"][0]["consumption_l_100km"] is None
    assert data["coverage"]["excluded_intervals"] == 1 and data["comparison"] is None
    history[-1].is_full_tank = False
    history[-1].save()
    detail = admin_client.get(
        f"/api/v1/vehicles/{car.pk}/consumption-intervals/detail/?{PARAMS}&start_id={history[0].pk}&end_id={history[-1].pk}"
    )
    assert detail.status_code == 404


def test_consistent_snapshot_during_concurrent_write(users, car, history):
    barrier = Barrier(2)

    def read():
        try:
            actor = User.objects.get(pk=users["admin"].pk)
            request = SimpleNamespace(user=actor, session={"auth_epoch": actor.auth_epoch})
            with services.snapshot(request):
                before = Refueling.objects.get(pk=history[1].pk).liters
                barrier.wait(timeout=10)
                barrier.wait(timeout=10)
                after = Refueling.objects.get(pk=history[1].pk).liters
                return before, after
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(read)
        barrier.wait(timeout=10)
        Refueling.objects.filter(pk=history[1].pk).update(liters=Decimal("15"))
        barrier.wait(timeout=10)
        assert future.result(timeout=10) == (Decimal("20"), Decimal("20"))
    assert Refueling.objects.get(pk=history[1].pk).liters == 15


def test_interval_pagination_filters_and_foreign_boundary_ids(admin_client, car, history, users):
    url = f"/api/v1/vehicles/{car.pk}/consumption-intervals/"
    response = admin_client.get(url + f"?{PARAMS}&page_size=1")
    assert response.status_code == 200
    assert response.json()["count"] == 1 and response.json()["next"] is None
    assert admin_client.get(url + f"?{PARAMS}&vehicle_id={users['user'].pk}").status_code == 400
    assert admin_client.get(url + f"?{PARAMS}&page_size=101").status_code == 400
    assert admin_client.get(url + f"?{PARAMS}&page=2").status_code == 404
    assert (
        admin_client.get(
            url + f"detail/?{PARAMS}&start_id={users['user'].pk}&end_id={history[-1].pk}"
        ).status_code
        == 404
    )


def test_same_fuel_weighted_aggregation_and_available_choices(admin_client, car, history, users):
    other = Vehicle.objects.create(
        owner=users["user"], name="Druhé auto", make="X", model="Y", fuel_type="PETROL", initial_odometer_km=0
    )
    for index, (km, liters) in enumerate([(0, 50), (500, 35)]):
        Refueling.objects.create(
            vehicle=other,
            date=date(2026, 2, 1 + index),
            day_sequence=1,
            liters=liters,
            total_amount=liters * 40,
            amount_source="ENTERED",
            fuel_type="PETROL",
            odometer_km=km,
            is_full_tank=True,
            created_by=users["user"],
            updated_by=users["user"],
        )
    data = admin_client.get(BASE + "?" + PARAMS).json()
    assert data["consumption_l_100km"] == "7.272727"
    assert data["coverage"]["distance_km"] == 1100
    selected = admin_client.get(BASE + f"?{PARAMS}&vehicle_id={car.pk}").json()
    assert {v["id"] for v in selected["available_vehicles"]} == {str(car.pk), str(other.pk)}
    assert len(selected["coverage"]["vehicles"]) == 1


def test_same_day_reorder_recomputes_and_concurrent_stale_order_is_rejected(admin_client, car, history):
    from rest_framework.test import APIClient

    with transaction.atomic():
        for position, item in enumerate(history, 1):
            item.date = date(2026, 2, 1)
            item.day_sequence = position
            item.save()
    url = f"/api/v1/vehicles/{car.pk}/refueling-order/"
    original = admin_client.get(url + "?date=2026-02-01")
    barrier = Barrier(2)

    def attempt(order):
        try:
            client = APIClient(enforce_csrf_checks=True)
            assert login(client).status_code == 200
            token = csrf(client)
            barrier.wait(timeout=10)
            return client.put(
                url,
                {"date": "2026-02-01", "ordered_ids": [str(history[i].pk) for i in order]},
                format="json",
                HTTP_X_CSRFTOKEN=token,
                HTTP_IF_MATCH=original["ETag"],
            ).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, [[0, 2, 1], [2, 1, 0]]))
    assert sorted(results) == [200, 412]
    data = admin_client.get(BASE + f"?{PARAMS}&vehicle_id={car.pk}").json()
    assert data["consumption_l_100km"] is None
    assert data["coverage"]["excluded_intervals"] == 1


def test_create_racing_revoked_grant_never_writes_after_revocation(admin_client, car, users):
    import uuid

    from rest_framework.test import APIClient

    grant = VehicleAccess.objects.create(
        vehicle=car, user=users["other"], role="CONTRIBUTOR", granted_by=users["admin"]
    )
    grant_url = f"/api/v1/admin/vehicle-access/{grant.pk}/"
    original = admin_client.get(grant_url)
    barrier = Barrier(2)

    def attempt(action):
        try:
            client = APIClient(enforce_csrf_checks=True)
            assert login(client, "other" if action == "create" else "admin").status_code == 200
            token = csrf(client)
            barrier.wait(timeout=10)
            if action == "create":
                return client.post(
                    "/api/v1/refuelings/",
                    {
                        "vehicle_id": str(car.pk),
                        "date": "2026-02-01",
                        "liters": "20",
                        "total_amount": "800",
                        "odometer_km": 100,
                    },
                    format="json",
                    HTTP_X_CSRFTOKEN=token,
                    HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
                ).status_code
            return client.delete(
                grant_url, HTTP_X_CSRFTOKEN=token, HTTP_IF_MATCH=original["ETag"]
            ).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        created, revoked = list(pool.map(attempt, ["create", "revoke"]))
    assert revoked == 204 and created in [201, 404]
    assert Refueling.objects.filter(vehicle=car).count() == (1 if created == 201 else 0)
    client = APIClient(enforce_csrf_checks=True)
    assert login(client, "other").status_code == 200
    assert client.get(BASE + f"?{PARAMS}&vehicle_id={car.pk}").status_code == 404
    assert client.get(BASE + f"?{PARAMS}").json()["available_vehicles"] == []
