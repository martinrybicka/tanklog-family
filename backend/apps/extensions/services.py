import csv
import hashlib
import io
import json
import uuid
from datetime import timedelta
from types import SimpleNamespace

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import record
from apps.core.errors import Problem
from apps.refuelings import services as fuel
from apps.refuelings.models import Refueling
from apps.refuelings.serializers import RefuelingInput
from apps.vehicles.selectors import effective_role, vehicle_for, vehicles_for
from apps.vehicles.services import lock_users, lock_vehicle

from .models import ExtensionRequest, ImportBatch, VehicleEvent
from .rules import energy_totals, reminder_state
from .serializers import EventInput


def tag(item):
    return f'"event:{item.pk}:{item.version}"'


def authorize(user, car, item=None, delete=False):
    role = effective_role(user, car)
    if role in ["OWNER", "ADMIN"] and (item is not None or car.status == "ACTIVE"):
        return
    if (
        role == "CONTRIBUTOR"
        and car.status == "ACTIVE"
        and not delete
        and (item is None or item.author_id == user.pk)
    ):
        return
    raise Problem("permission_denied", "Tuto událost nemůžete změnit.", 403)


def events_for(user):
    return VehicleEvent.objects.filter(vehicle__in=vehicles_for(user)).select_related("vehicle")


@transaction.atomic
def save_event(request, vehicle_id, data, item_id=None, delete=False):
    lock_users(request)
    car = lock_vehicle(request, vehicle_id, manage=False)
    item = (
        get_object_or_404(events_for(request.user).select_for_update(), pk=item_id, vehicle=car)
        if item_id
        else None
    )
    if item:
        authorize(request.user, car, item, delete)
        fuel.require_tag(request, tag(item))
        if delete:
            record(request, "event.deleted", item, vehicle_id=car.pk)
            item.delete()
            fuel.bump(car)
            return None
    else:
        try:
            key = uuid.UUID(request.headers.get("Idempotency-Key", ""))
        except ValueError, TypeError:
            raise ValidationError({"idempotency_key": "Vyžadováno UUID Idempotency-Key."})
        digest = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
        previous = ExtensionRequest.objects.filter(user=request.user, key=key).first()
        if previous:
            if previous.payload_hash != digest or previous.vehicle_id != car.pk:
                raise Problem("idempotency_conflict", "Klíč již patří jinému obsahu.", 409)
            return get_object_or_404(events_for(request.user), pk=previous.result_id)
        authorize(request.user, car)
        item = VehicleEvent(vehicle=car, author=request.user)
    old_values = (
        {name: str(getattr(item, name)) for name in EventInput().fields} if not item._state.adding else {}
    )
    new = item.pk is None or item._state.adding
    for name, value in data.items():
        setattr(item, name, value)
    if not new:
        item.version += 1
    if item.kind != "ENERGY":
        item.quantity, item.unit = None, ""
    item.save()
    fuel.bump(car)
    if new:
        ExtensionRequest.objects.create(
            user=request.user,
            key=key,
            vehicle=car,
            payload_hash=digest,
            result_id=item.pk,
        )
    record(
        request,
        "event.created" if new else "event.updated",
        item,
        {
            "from": old_values,
            "to": {name: str(getattr(item, name)) for name in EventInput().fields},
        },
        vehicle_id=car.pk,
    )
    return item


def reading(car):
    values = []
    row = (
        Refueling.objects.filter(vehicle=car, odometer_km__isnull=False, date__lte=timezone.localdate())
        .order_by("-date", "-day_sequence", "-id")
        .first()
    )
    if row:
        values.append((row.date, row.odometer_km))
    event = (
        VehicleEvent.objects.filter(vehicle=car, odometer_km__isnull=False, date__lte=timezone.localdate())
        .order_by("-date", "-created_at")
        .first()
    )
    if event:
        values.append((event.date, event.odometer_km))
    return max(values, key=lambda value: value[0])[1] if values else car.initial_odometer_km


def reminders(user):
    result = []
    cars = {}
    for item in events_for(user).filter(closed=False, vehicle__status="ACTIVE"):
        if not item.due_date and item.due_odometer_km is None:
            continue
        km = (
            cars.setdefault(item.vehicle_id, reading(item.vehicle))
            if item.vehicle_id not in cars
            else cars[item.vehicle_id]
        )
        state = reminder_state(
            timezone.localdate(),
            item.due_date,
            item.due_odometer_km,
            km,
            item.notice_days,
            item.notice_km,
        )
        result.append(
            {
                "id": str(item.pk),
                "vehicle_id": str(item.vehicle_id),
                "vehicle_name": item.vehicle.name,
                "title": item.title,
                "due_date": item.due_date,
                "due_odometer_km": item.due_odometer_km,
                "reading_km": km,
                "state": state,
            }
        )
    return sorted(
        result,
        key=lambda value: (
            {"OVERDUE": 0, "SOON": 1, "UNKNOWN": 2, "LATER": 3}[value["state"]],
            str(value["due_date"] or "9999"),
        ),
    )


def totals(user, vehicle_id):
    car = vehicle_for(user, vehicle_id)
    rows = VehicleEvent.objects.filter(vehicle=car, kind="ENERGY").values_list("unit", "quantity", "amount")
    return energy_totals(rows)


def parse_csv(text, kind):
    if len(text.encode("utf-8")) > 128 * 1024:
        raise ValidationError("CSV přesahuje 128 KiB.")
    stream = io.StringIO(text.lstrip("\ufeff"))
    delimiter = ";" if ";" in text.split("\n", 1)[0] else ","
    parser = csv.DictReader(stream, delimiter=delimiter, strict=True)
    allowed = set(EventInput().fields if kind == "EVENT" else RefuelingInput().fields) - {
        "vehicle_id",
        "paid_by_user_id",
        "confirmed_warning_codes",
    }
    if (
        not parser.fieldnames
        or len(set(parser.fieldnames)) != len(parser.fieldnames)
        or set(parser.fieldnames) - allowed
    ):
        raise ValidationError("CSV má chybějící, duplicitní nebo nepovolené záhlaví.")
    result = []
    try:
        for row in parser:
            if len(result) >= 200:
                raise ValidationError("Nejvýše 200 řádků.")
            if None in row or any(v is None for v in row.values()):
                raise ValidationError("Počet sloupců nesouhlasí.")
            result.append(
                {
                    k: (
                        v.replace(",", ".")
                        if k
                        in {
                            "liters",
                            "unit_price_entered",
                            "total_amount",
                            "amount",
                            "quantity",
                        }
                        else v
                    )
                    for k, v in row.items()
                    if v != ""
                }
            )
    except csv.Error as error:
        raise ValidationError("CSV má neplatné uvozovky nebo strukturu.") from error
    if not result:
        raise ValidationError("CSV neobsahuje žádný řádek.")
    return result


@transaction.atomic
def preview_import(request, vehicle_id, data):
    lock_users(request)
    car = lock_vehicle(request, vehicle_id, manage=False)
    if data["kind"] == "FUEL":
        fuel.authorize(request.user, car, "create")
    else:
        authorize(request.user, car)
    rows = parse_csv(data["csv_text"], data["kind"])
    validated = []
    errors = []
    warnings = []
    for index, row in enumerate(rows):
        serializer = (EventInput if data["kind"] == "EVENT" else RefuelingInput)(
            data=row if data["kind"] == "EVENT" else row | {"vehicle_id": str(car.pk)}
        )
        if not serializer.is_valid():
            errors.append({"row": index + 1, "fields": serializer.errors})
            validated.append({})
            continue
        values = serializer.validated_data
        try:
            if data["kind"] == "FUEL":
                prepared = fuel.prepare(car, values)
                from apps.refuelings.quality import warnings_for

                warnings.extend({"row": index + 1, **warning} for warning in warnings_for(car, prepared))
            validated.append(json.loads(json.dumps(values, default=str)))
        except (ValidationError, Problem) as error:
            validated.append({})
            errors.append({"row": index + 1, "message": str(error.detail)})
    with transaction.atomic():
        lock_users(request)
        current = lock_vehicle(request, car.pk, manage=False)
        (
            fuel.authorize(request.user, current, "create")
            if data["kind"] == "FUEL"
            else authorize(request.user, current)
        )
        return ImportBatch.objects.create(
            user=request.user,
            vehicle=current,
            kind=data["kind"],
            vehicle_version=current.version,
            history_revision=current.history_revision,
            raw=data["csv_text"],
            rows=validated,
            errors=errors,
            warnings=warnings,
        )


@transaction.atomic
def confirm_import(request, batch_id, codes):
    lock_users(request)
    batch = get_object_or_404(ImportBatch.objects.select_for_update(), pk=batch_id, user=request.user)
    car = lock_vehicle(request, batch.vehicle_id, manage=False)
    if batch.completed:
        return batch
    if batch.created_at < timezone.now() - timedelta(hours=24):
        raise Problem("expired", "Návrh importu vypršel.", 409)
    if (car.version, car.history_revision) != (
        batch.vehicle_version,
        batch.history_revision,
    ):
        raise Problem(
            "stale_import",
            "Historie nebo údaje auta se změnily. Vytvořte nový náhled.",
            412,
        )
    if batch.errors:
        raise ValidationError("Opravte chyby CSV a vytvořte nový náhled.")
    (fuel.authorize(request.user, car, "create") if batch.kind == "FUEL" else authorize(request.user, car))
    results = []
    for index, row in enumerate(batch.rows):
        headers = {"Idempotency-Key": str(uuid.uuid5(batch.pk, str(index)))}
        child = SimpleNamespace(
            user=request.user,
            session=request.session,
            headers=headers,
            request_id=getattr(request, "request_id", ""),
        )
        if batch.kind == "FUEL":
            serializer = RefuelingInput(data=row | {"confirmed_warning_codes": codes})
            serializer.is_valid(raise_exception=True)
            try:
                item, _ = fuel.create(child, serializer.validated_data)
            except Problem as error:
                if hasattr(error, "extra") and "warnings" in error.extra:
                    error.extra = {
                        "warnings": [{**warning, "row": index + 1} for warning in error.extra["warnings"]]
                    }
                raise
        else:
            serializer = EventInput(data=row)
            serializer.is_valid(raise_exception=True)
            item = save_event(child, car.pk, serializer.validated_data)
        results.append(str(item.pk))
    batch.completed = True
    batch.results = results
    batch.save(update_fields=["completed", "results"])
    record(
        request,
        "import.confirmed",
        batch,
        {"count": len(results), "kind": batch.kind},
        vehicle_id=car.pk,
    )
    return batch
