from django.db.models import Exists, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404

from .models import Vehicle, VehicleAccess


def vehicles_for(user):
    grants = VehicleAccess.objects.filter(vehicle_id=OuterRef("pk"), user=user)
    queryset = Vehicle.objects.annotate(access_role=Subquery(grants.values("role")[:1]))
    if not user.is_active or user.must_change_password:
        return queryset.none()
    if user.system_role != "ADMIN":
        queryset = queryset.filter(Q(owner=user) | Exists(grants))
    return queryset


def vehicle_for(user, vehicle_id):
    return get_object_or_404(vehicles_for(user), pk=vehicle_id)


def effective_role(user, vehicle):
    if user.system_role == "ADMIN":
        return "ADMIN"
    if vehicle.owner_id == user.pk:
        return "OWNER"
    return vehicle.access_role


def permissions(user, vehicle):
    manage = effective_role(user, vehicle) in ["ADMIN", "OWNER"]
    return {
        "edit": manage,
        "archive": manage and vehicle.status == "ACTIVE",
        "restore": manage and vehicle.status == "ARCHIVED",
        "manage_access": user.system_role == "ADMIN",
        "create_refueling": vehicle.status == "ACTIVE"
        and effective_role(user, vehicle) in ["ADMIN", "OWNER", "CONTRIBUTOR"],
    }
