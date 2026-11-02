import hashlib
import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import record
from apps.core.errors import Problem
from apps.vehicles.selectors import vehicle_for
from apps.vehicles.services import lock_users, lock_vehicle

from .amounts import resolve_amount
from .models import Refueling, RequestDeduplication
from .quality import warnings_for
from .selectors import payer_options, refueling_for, rights


def etag(item):
    return f'"refueling:{item.pk}:{item.version}"'


def history_etag(vehicle):
    return f'"history:{vehicle.pk}:{vehicle.history_revision}"'


def require_tag(request, expected):
    if not request.headers.get("If-Match"):
        raise Problem("precondition_required", "Nejdříve načtěte aktuální záznam.", 428)
    if request.headers["If-Match"] != expected:
        raise Problem("stale_version", "Záznam se mezitím změnil. Načtěte jej znovu.", 412)


def authorize(user, vehicle, action, item=None):
    if not rights(user, vehicle, item)[action]:
        raise Problem("permission_denied", "K této změně nemáte oprávnění nebo je vozidlo archivované.", 403)


def bump(vehicle):
    vehicle.history_revision += 1
    vehicle.save(update_fields=["history_revision", "updated_at"])


def audit(request, action, item, changes=None):
    record(request, action, item, changes, vehicle_id=item.vehicle_id)


def snapshot(item):
    return {
        f.name: str(getattr(item, f.attname)) if getattr(item, f.attname) is not None else None
        for f in Refueling._meta.fields
        if f.name not in ["created_at", "updated_at"]
    }


def ensure_warnings(vehicle, values, confirmed, item=None):
    warnings = warnings_for(vehicle, values, item)
    if set(w["code"] for w in warnings) - set(confirmed):
        error = Problem("confirmation_required", "Zkontrolujte a potvrďte upozornění před uložením.", 409)
        error.extra = {"warnings": warnings}
        raise error
    return warnings


def prepare(vehicle, data, item=None):
    fields = [
        "date",
        "liters",
        "unit_price_entered",
        "total_amount",
        "odometer_km",
        "is_full_tank",
        "break_before",
        "fuel_type",
        "station_code",
        "station_custom_name",
        "note",
        "paid_by_user_id",
        "paid_by_label",
    ]
    values = (
        {key: getattr(item, key) for key in fields}
        if item
        else {
            "date": timezone.localdate(),
            "unit_price_entered": None,
            "odometer_km": None,
            "is_full_tank": False,
            "break_before": False,
            "fuel_type": vehicle.fuel_type,
            "station_code": "",
            "station_custom_name": "",
            "note": "",
            "paid_by_user_id": None,
            "paid_by_label": "",
        }
    )
    values.update({key: value for key, value in data.items() if key in fields})
    amount_input = dict(values)
    if "total_amount" not in data:
        amount_input.pop("total_amount", None)
    total, source = resolve_amount(
        amount_input,
        {"total_amount": item.total_amount, "amount_source": item.amount_source} if item else None,
    )
    if total > Decimal("999999999999.99"):
        raise ValidationError({"total_amount": "Částka přesahuje povolený rozsah."})
    values.update(total_amount=total, amount_source=source)
    if values["paid_by_user_id"] and values["paid_by_label"]:
        raise ValidationError({"paid_by_label": "Zvolte uživatele nebo volný název plátce, nikoli obojí."})
    if (
        values["paid_by_user_id"]
        and (not item or values["paid_by_user_id"] != item.paid_by_user_id)
        and not payer_options(vehicle).filter(pk=values["paid_by_user_id"]).exists()
    ):
        raise ValidationError({"paid_by_user_id": "Vyberte aktivního plátce s přístupem k tomuto autu."})
    if values["station_code"] == "OTHER" and not values["station_custom_name"]:
        raise ValidationError({"station_custom_name": "Uveďte název ostatní stanice."})
    if values["station_code"] != "OTHER" and values["station_custom_name"]:
        raise ValidationError({"station_custom_name": "Vlastní název je možný pouze u stanice Ostatní."})
    date = values["date"]
    count = Refueling.objects.filter(vehicle=vehicle, date=date).exclude(pk=item.pk if item else None).count()
    default = item.day_sequence if item and item.date == date else count + 1
    values["day_sequence"] = data.get("day_sequence", default)
    if values["day_sequence"] > count + 1:
        raise ValidationError({"day_sequence": f"Pozice musí být mezi 1 a {count + 1}."})
    return values


def renumber(request, vehicle, date, moving=None, position=None):
    records = list(
        Refueling.objects.filter(vehicle=vehicle, date=date)
        .exclude(pk=moving.pk if moving else None)
        .order_by("day_sequence", "id")
    )
    if moving is not None:
        records.insert(position - 1, moving)
    changed = []
    for i, row in enumerate(records, 1):
        if row.day_sequence != i:
            row.day_sequence = i
            row.version += 1
            row.updated_by = request.user
            row.updated_at = timezone.now()
            changed.append(row)
    if changed:
        Refueling.objects.bulk_update(changed, ["day_sequence", "version", "updated_by", "updated_at"])
        record(
            request,
            "refueling.order_changed",
            vehicle,
            {"date": str(date), "ordered_ids": [str(row.pk) for row in records]},
            vehicle_id=vehicle.pk,
        )


@transaction.atomic
def create(request, data):
    try:
        key = uuid.UUID(request.headers.get("Idempotency-Key", ""))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValidationError(
            {"idempotency_key": "Požadavek musí mít Idempotency-Key ve formátu UUID."}
        ) from error
    # Před zamykáním cílového účtu nesmí tělo prozradit cizí roster.
    existing_key = RequestDeduplication.objects.filter(user=request.user, key=key).exists()
    target_id = None if existing_key else data.get("paid_by_user_id")
    if not existing_key:
        initial_vehicle = vehicle_for(request.user, data["vehicle_id"])
        authorize(request.user, initial_vehicle, "create")
        if target_id and not payer_options(initial_vehicle).filter(pk=target_id).exists():
            raise ValidationError({"paid_by_user_id": "Vyberte aktivního plátce s přístupem k tomuto autu."})
    lock_users(request, target_id)
    payload_hash = hashlib.sha256(
        json.dumps(
            {k: v for k, v in data.items() if k != "confirmed_warning_codes"}, sort_keys=True, default=str
        ).encode()
    ).hexdigest()
    previous = RequestDeduplication.objects.filter(user=request.user, key=key).first()
    if previous:
        item = refueling_for(request.user, previous.result_id)
        if previous.payload_hash != payload_hash:
            raise Problem("idempotency_conflict", "Tento klíč už byl použit pro jiný obsah.", 409)
        if previous.expires_at <= timezone.now():
            raise Problem(
                "idempotency_expired",
                "Platnost opakování vypršela. Ověřte existující záznam v historii.",
                409,
            )
        return item, True
    vehicle = lock_vehicle(request, data["vehicle_id"], manage=False)
    authorize(request.user, vehicle, "create")
    values = prepare(vehicle, data)
    warnings = ensure_warnings(vehicle, values, data.get("confirmed_warning_codes", []))
    item = Refueling.objects.create(
        vehicle=vehicle, created_by=request.user, updated_by=request.user, **values
    )
    renumber(request, vehicle, item.date, item, values["day_sequence"])
    bump(vehicle)
    audit(
        request,
        "refueling.created",
        item,
        {"values": snapshot(item), "confirmed_warning_codes": [w["code"] for w in warnings]},
    )
    RequestDeduplication.objects.create(
        user=request.user,
        key=key,
        payload_hash=payload_hash,
        result_id=item.pk,
        expires_at=timezone.now() + timedelta(hours=24),
    )
    return refueling_for(request.user, item.pk), False


def locked_item(request, item_id, data=None):
    initial = refueling_for(request.user, item_id)
    target_id = (data or {}).get("paid_by_user_id")
    if target_id == initial.paid_by_user_id:
        target_id = None
    if target_id:
        initial_vehicle = vehicle_for(request.user, initial.vehicle_id)
        authorize(request.user, initial_vehicle, "edit", initial)
        if not payer_options(initial_vehicle).filter(pk=target_id).exists():
            raise ValidationError({"paid_by_user_id": "Vyberte aktivního plátce s přístupem k tomuto autu."})
    lock_users(request, target_id)
    vehicle = lock_vehicle(request, initial.vehicle_id, manage=False)
    item = refueling_for(request.user, item_id)
    require_tag(request, etag(item))
    return item, vehicle


@transaction.atomic
def update(request, item_id, data):
    item, vehicle = locked_item(request, item_id, data)
    authorize(request.user, vehicle, "edit", item)
    old = snapshot(item)
    old_date = item.date
    values = prepare(vehicle, data, item)
    warnings = ensure_warnings(vehicle, values, data.get("confirmed_warning_codes", []), item)
    for key, value in values.items():
        setattr(item, key, value)
    item.updated_by = request.user
    item.version += 1
    item.save()
    if old_date != item.date:
        renumber(request, vehicle, old_date)
    renumber(request, vehicle, item.date, item, values["day_sequence"])
    bump(vehicle)
    audit(
        request,
        "refueling.updated",
        item,
        {"from": old, "to": snapshot(item), "confirmed_warning_codes": [w["code"] for w in warnings]},
    )
    return refueling_for(request.user, item.pk)


@transaction.atomic
def delete(request, item_id):
    item, vehicle = locked_item(request, item_id)
    authorize(request.user, vehicle, "delete", item)
    audit(request, "refueling.deleted", item, snapshot(item))
    date = item.date
    item.delete()
    renumber(request, vehicle, date)
    bump(vehicle)


@transaction.atomic
def reorder(request, vehicle_id, data):
    lock_users(request)
    vehicle = lock_vehicle(request, vehicle_id, manage=False)
    authorize(request.user, vehicle, "reorder")
    require_tag(request, history_etag(vehicle))
    items = {r.pk: r for r in Refueling.objects.filter(vehicle=vehicle, date=data["date"])}
    ids = data["ordered_ids"]
    if len(ids) != len(set(ids)) or set(ids) != set(items):
        raise ValidationError(
            {"ordered_ids": "Pořadí musí obsahovat přesně všechny záznamy tohoto dne jednou."}
        )
    changed = []
    for i, key in enumerate(ids, 1):
        item = items[key]
        if item.day_sequence != i:
            item.day_sequence = i
            item.version += 1
            item.updated_by = request.user
            item.updated_at = timezone.now()
            changed.append(item)
    if changed:
        Refueling.objects.bulk_update(changed, ["day_sequence", "version", "updated_by", "updated_at"])
    bump(vehicle)
    record(
        request,
        "refueling.order_changed",
        vehicle,
        {"date": str(data["date"]), "ordered_ids": [str(pk) for pk in ids]},
        vehicle_id=vehicle.pk,
    )
    return vehicle
