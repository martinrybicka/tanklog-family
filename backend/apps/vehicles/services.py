from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.services import check_session, reauthenticate
from apps.audit.models import record
from apps.core.errors import Problem

from .models import Vehicle, VehicleAccess
from .selectors import vehicle_for


def etag(obj):
    kind = "vehicle" if isinstance(obj, Vehicle) else "vehicle-access"
    return f'"{kind}:{obj.pk}:{obj.version}"'


def require_version(request, obj):
    supplied = request.headers.get("If-Match")
    if not supplied:
        raise Problem("precondition_required", "Nejdříve načtěte aktuální údaje.", 428)
    if supplied != etag(obj):
        raise Problem("stale_version", "Údaje se mezitím změnily. Načtěte je znovu.", 412)


def lock_users(request, target_id=None, admin=False):
    # Účty vždy před vozidlem a ve stabilním pořadí; deaktivace tak nesoutěží se zápisem.
    ids = {request.user.pk, target_id} - {None}
    users = {u.pk: u for u in User.objects.select_for_update().filter(pk__in=ids).order_by("pk")}
    actor = users[request.user.pk]
    check_session(request, actor)
    if actor.must_change_password or request.session.get("password_change_only"):
        raise Problem("password_change_required", "Nejdříve nastavte vlastní heslo.", 403)
    if admin and actor.system_role != "ADMIN":
        raise Problem("permission_denied", "Tato akce je pouze pro administrátora.", 403)
    request.user = actor
    target = users.get(target_id)
    if target_id and (target is None or not target.is_active):
        raise serializers.ValidationError({"user_id": "Vyberte aktivní účet."})
    return actor, target


def lock_vehicle(request, vehicle_id, manage=True):
    # Zamyká se fyzický řádek, potom se pod stejným zámkem znovu ověřuje přístup.
    get_object_or_404(Vehicle.objects.select_for_update(), pk=vehicle_id)
    vehicle = vehicle_for(request.user, vehicle_id)
    if manage and request.user.system_role != "ADMIN" and vehicle.owner_id != request.user.pk:
        raise Problem(
            "permission_denied",
            "Údaje vozidla mění pouze vlastník nebo administrátor.",
            403,
        )
    return vehicle


def save_vehicle(vehicle):
    try:
        with transaction.atomic():
            vehicle.save()
    except IntegrityError as error:
        # VIN nikdy neprozradí existenci, vlastníka ani identifikátor cizího auta.
        if (
            getattr(error.__cause__, "diag", None)
            and error.__cause__.diag.constraint_name == "vehicles_vehicle_vin_key"
        ):
            raise serializers.ValidationError(
                {"vin": "Tento VIN nelze použít. Zkontrolujte údaje nebo kontaktujte správce."}
            ) from error
        raise


def audit(request, action, obj, changes=None):
    record(
        request,
        action,
        obj,
        changes,
        vehicle_id=obj.pk if isinstance(obj, Vehicle) else obj.vehicle_id,
    )


def bump(vehicle):
    vehicle.version += 1
    vehicle.save(update_fields=["version", "updated_at"])


@transaction.atomic
def create_vehicle(request, data):
    lock_users(request)
    data = dict(data)
    lookup_id = data.pop("lookup_id", None)
    lookup_fields = data.pop("lookup_fields", [])
    normalize_energy(data)
    vehicle = Vehicle(owner=request.user, **data)
    save_vehicle(vehicle)
    if lookup_id:
        from apps.extensions.integrations import confirm_lookup

        confirm_lookup(request, vehicle, lookup_id, lookup_fields)
    audit(request, "vehicle.created", vehicle)
    return vehicle_for(request.user, vehicle.pk)


@transaction.atomic
def update_vehicle(request, vehicle_id, data):
    lock_users(request)
    vehicle = lock_vehicle(request, vehicle_id)
    require_version(request, vehicle)
    data = dict(data)
    lookup_id = data.pop("lookup_id", None)
    lookup_fields = data.pop("lookup_fields", [])
    normalize_energy(data, vehicle)
    changes = {}
    for key, value in data.items():
        old = getattr(vehicle, key)
        if old != value:
            changes[key] = {
                "from": str(old) if old is not None else None,
                "to": str(value) if value is not None else None,
            }
            setattr(vehicle, key, value)
    if changes:
        vehicle.version += 1
        if set(changes) & {
            "initial_odometer_km",
            "fuel_type",
            "tank_capacity_l",
            "consumption_mode",
        }:
            vehicle.history_revision += 1
        save_vehicle(vehicle)
        audit(request, "vehicle.updated", vehicle, changes)
    if lookup_id:
        from apps.extensions.integrations import confirm_lookup

        confirm_lookup(request, vehicle, lookup_id, lookup_fields)
    return vehicle_for(request.user, vehicle.pk)


def normalize_energy(data, vehicle=None):
    fuel = data.get("fuel_type", vehicle.fuel_type if vehicle else "PETROL")
    if fuel in ["CNG", "ELECTRIC"]:
        data.update(
            consumption_mode="UNSUPPORTED_UNIT",
            standard_consumption_l_100km=None,
            standard_methodology="UNKNOWN",
            standard_source="",
            standard_source_note="",
        )
    elif (
        vehicle
        and vehicle.consumption_mode == "UNSUPPORTED_UNIT"
        and data.get("consumption_mode", "UNSUPPORTED_UNIT") == "UNSUPPORTED_UNIT"
    ):
        data["consumption_mode"] = "SINGLE_TANK"


@transaction.atomic
def archive_vehicle(request, vehicle_id, archived):
    lock_users(request)
    vehicle = lock_vehicle(request, vehicle_id)
    require_version(request, vehicle)
    status = "ARCHIVED" if archived else "ACTIVE"
    if vehicle.status != status:
        vehicle.status = status
        vehicle.archived_at = timezone.now() if archived else None
        vehicle.version += 1
        vehicle.save()
        audit(request, "vehicle.archived" if archived else "vehicle.restored", vehicle)
    return vehicle_for(request.user, vehicle.pk)


@transaction.atomic
def create_access(request, vehicle_id, data):
    actor, user = lock_users(request, data["user_id"], admin=True)
    vehicle = lock_vehicle(request, vehicle_id)
    if vehicle.owner_id == user.pk:
        raise Problem(
            "owner_grant",
            "Vlastník má přístup automaticky; grant mu nelze přidělit.",
            409,
        )
    if VehicleAccess.objects.filter(vehicle=vehicle, user=user).exists():
        raise Problem("duplicate_access", "Tento účet již má k vozidlu přístup.", 409)
    grant = VehicleAccess.objects.create(vehicle=vehicle, user=user, role=data["role"], granted_by=actor)
    bump(vehicle)
    audit(
        request,
        "vehicle.access_created",
        grant,
        {"user_id": str(user.pk), "role": grant.role},
    )
    return grant


@transaction.atomic
def change_access(request, access_id, data=None):
    # Pomocné čtení neurčuje oprávnění; po zámku vozidla čteme grant znovu.
    initial = get_object_or_404(VehicleAccess, pk=access_id)
    lock_users(request, initial.user_id if data is not None else None, admin=True)
    vehicle = lock_vehicle(request, initial.vehicle_id)
    grant = get_object_or_404(VehicleAccess.objects.select_related("user"), pk=access_id)
    require_version(request, grant)
    if data is None:
        audit(
            request,
            "vehicle.access_removed",
            grant,
            {"user_id": str(grant.user_id), "role": grant.role},
        )
        grant.delete()
    elif grant.role != data["role"]:
        previous = grant.role
        grant.role = data["role"]
        grant.version += 1
        grant.save()
        audit(
            request,
            "vehicle.access_updated",
            grant,
            {"role": {"from": previous, "to": grant.role}},
        )
    bump(vehicle)
    return grant


def transfer_owner(request, vehicle_id, data):
    reauthenticate(request, request.user, data["current_password"])
    return _transfer_locked(request, vehicle_id, data)


@transaction.atomic
def _transfer_locked(request, vehicle_id, data):
    actor, new_owner = lock_users(request, data["new_owner_id"], admin=True)
    vehicle = lock_vehicle(request, vehicle_id)
    require_version(request, vehicle)
    if vehicle.owner_id == new_owner.pk:
        raise Problem("same_owner", "Tento účet již vozidlo vlastní.", 409)
    previous_id = vehicle.owner_id
    # Žádná další operace nedokáže vložit grant vlastníkovi mezi tyto kroky.
    VehicleAccess.objects.filter(vehicle=vehicle, user_id__in=[previous_id, new_owner.pk]).delete()
    vehicle.owner = new_owner
    vehicle.version += 1
    vehicle.save()
    role = data.get("previous_owner_role")
    if role:
        VehicleAccess.objects.create(vehicle=vehicle, user_id=previous_id, role=role, granted_by=actor)
    audit(
        request,
        "vehicle.owner_transferred",
        vehicle,
        {
            "from_owner_id": str(previous_id),
            "to_owner_id": str(new_owner.pk),
            "previous_owner_role": role,
        },
    )
    return vehicle_for(actor, vehicle.pk)
