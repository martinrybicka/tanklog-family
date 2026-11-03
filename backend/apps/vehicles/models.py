import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Vehicle(models.Model):
    class Fuel(models.TextChoices):
        CNG = "CNG", "CNG (kg)"
        ELECTRIC = "ELECTRIC", "Elektřina (kWh)"
        PETROL = "PETROL", "Benzín"
        DIESEL = "DIESEL", "Nafta"
        LPG = "LPG", "LPG"
        ETHANOL = "ETHANOL", "Ethanol"
        OTHER_LIQUID = "OTHER_LIQUID", "Jiné kapalné palivo"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Aktivní"
        ARCHIVED = "ARCHIVED", "Archivované"

    class ConsumptionMode(models.TextChoices):
        UNSUPPORTED_UNIT = "UNSUPPORTED_UNIT", "Jiné jednotky (kg/kWh)"
        SINGLE_TANK = "SINGLE_TANK", "Jedna nádrž"
        UNSUPPORTED_MULTI_TANK = "UNSUPPORTED_MULTI_TANK", "Více nádrží"

    class Methodology(models.TextChoices):
        WLTP = "WLTP", "WLTP"
        NEDC = "NEDC", "NEDC"
        MANUFACTURER = "MANUFACTURER", "Výrobce"
        USER_ESTIMATE = "USER_ESTIMATE", "Vlastní odhad"
        UNKNOWN = "UNKNOWN", "Neznámá"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="vehicles")
    name = models.CharField(max_length=100)
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    manufacture_year = models.PositiveSmallIntegerField(null=True, blank=True)
    registration_plate = models.CharField(max_length=20, blank=True, default="")
    vin = models.CharField(max_length=17, null=True, blank=True, unique=True)
    fuel_type = models.CharField(max_length=20, choices=Fuel.choices)
    consumption_mode = models.CharField(
        max_length=30,
        choices=ConsumptionMode.choices,
        default=ConsumptionMode.SINGLE_TANK,
    )
    engine_displacement_cc = models.PositiveIntegerField(null=True, blank=True)
    power_kw = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    tank_capacity_l = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    standard_consumption_l_100km = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    standard_methodology = models.CharField(
        max_length=20, choices=Methodology.choices, default=Methodology.UNKNOWN
    )
    standard_source = models.CharField(max_length=500, blank=True, default="")
    standard_source_note = models.CharField(max_length=2000, blank=True, default="")
    initial_odometer_km = models.BigIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    version = models.PositiveBigIntegerField(default=1)
    history_revision = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name", "id"]
        indexes = [models.Index(fields=["owner", "status"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(initial_odometer_km__gte=0, initial_odometer_km__lte=99999999),
                name="vehicle_odometer_range",
            ),
            models.CheckConstraint(
                condition=Q(manufacture_year__isnull=True) | Q(manufacture_year__gte=1886),
                name="vehicle_year_min",
            ),
            models.CheckConstraint(
                condition=Q(status="ACTIVE", archived_at__isnull=True)
                | Q(status="ARCHIVED", archived_at__isnull=False),
                name="vehicle_archive_consistent",
            ),
            *[
                models.CheckConstraint(
                    condition=Q(**{f"{field}__isnull": True}) | Q(**{f"{field}__gt": 0}),
                    name=f"vehicle_positive_{field}",
                )
                for field in [
                    "engine_displacement_cc",
                    "power_kw",
                    "tank_capacity_l",
                    "standard_consumption_l_100km",
                ]
            ],
        ]


class VehicleAccess(models.Model):
    class Role(models.TextChoices):
        VIEWER = "VIEWER", "Čtenář"
        CONTRIBUTOR = "CONTRIBUTOR", "Přispěvatel"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="access_grants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="vehicle_grants",
    )
    role = models.CharField(max_length=15, choices=Role.choices)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["vehicle", "user"], name="unique_vehicle_user_grant"),
            models.CheckConstraint(
                condition=Q(role__in=["VIEWER", "CONTRIBUTOR"]),
                name="valid_vehicle_grant_role",
            ),
        ]
        indexes = [models.Index(fields=["user", "vehicle"])]
