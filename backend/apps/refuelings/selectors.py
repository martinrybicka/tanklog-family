from django.db.models import F, Q
from django.shortcuts import get_object_or_404

from apps.accounts.models import User
from apps.vehicles.models import VehicleAccess
from apps.vehicles.selectors import effective_role, vehicle_for, vehicles_for

from .models import Refueling


def refuelings_for(user):
    return Refueling.objects.filter(vehicle_id__in=vehicles_for(user).values("pk")).select_related(
        "vehicle", "created_by", "updated_by", "paid_by_user"
    )


def refueling_for(user, pk):
    return get_object_or_404(refuelings_for(user), pk=pk)


def rights(user, vehicle, item=None):
    role = effective_role(user, vehicle)
    manage = role in ["ADMIN", "OWNER"]
    contribute = role == "CONTRIBUTOR" and vehicle.status == "ACTIVE"
    return {
        "create": vehicle.status == "ACTIVE"
        and vehicle.fuel_type not in ["CNG", "ELECTRIC"]
        and (manage or contribute),
        "edit": manage or (contribute and item is not None and item.created_by_id == user.pk),
        "delete": manage,
        "reorder": manage,
    }


def payer_options(vehicle):
    grants = VehicleAccess.objects.filter(vehicle=vehicle).values("user_id")
    return (
        User.objects.filter(is_active=True)
        .filter(Q(pk=vehicle.owner_id) | Q(pk__in=grants) | Q(system_role="ADMIN"))
        .order_by("display_name", "username", "pk")
    )


def filtered(user, params):
    query = refuelings_for(user)
    if "vehicle_id" in params:
        vehicle_for(user, params["vehicle_id"])
        query = query.filter(vehicle_id=params["vehicle_id"])
    for key, lookup in [
        ("date_from", "date__gte"),
        ("date_to", "date__lte"),
        ("fuel_type", "fuel_type"),
        ("station_code", "station_code"),
    ]:
        if key in params:
            query = query.filter(**{lookup: params[key]})
    if params.get("search"):
        value = params["search"]
        station_codes = [
            code for code, label in Refueling.Station.choices if value.casefold() in label.casefold()
        ]
        query = query.filter(
            Q(vehicle__name__icontains=value)
            | Q(station_code__in=station_codes)
            | Q(station_code__icontains=value)
            | Q(station_custom_name__icontains=value)
            | Q(note__icontains=value)
        )
    order = params.get("ordering", "-date")
    descending = order.startswith("-")
    sign = "-" if descending else ""
    field = order.lstrip("-")
    first = F(field).desc(nulls_last=True) if descending else F(field).asc(nulls_last=True)
    secondary = [sign + "date"] if field != "date" else []
    return query.order_by(first, *secondary, sign + "day_sequence", sign + "id")
