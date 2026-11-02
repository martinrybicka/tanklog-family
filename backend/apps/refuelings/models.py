import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Length

from apps.vehicles.models import Vehicle


class Refueling(models.Model):
    class Station(models.TextChoices):
        ORLEN = "ORLEN", "ORLEN"
        SHELL = "SHELL", "Shell"
        MOL = "MOL", "MOL"
        OMV = "OMV", "OMV"
        EUROOIL = "EUROOIL", "EuroOil"
        TANK_ONO = "TANK_ONO", "Tank ONO"
        OTHER = "OTHER", "Ostatní"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="refuelings")
    date = models.DateField()
    day_sequence = models.PositiveIntegerField()
    liters = models.DecimalField(max_digits=10, decimal_places=3)
    unit_price_entered = models.DecimalField(max_digits=10, decimal_places=4, null=True)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    amount_source = models.CharField(
        max_length=10, choices=[("ENTERED", "Zadaná"), ("CALCULATED", "Vypočtená")]
    )
    odometer_km = models.BigIntegerField(null=True)
    is_full_tank = models.BooleanField(default=False)
    break_before = models.BooleanField(default=False)
    fuel_type = models.CharField(max_length=20, choices=Vehicle.Fuel.choices)
    station_code = models.CharField(max_length=10, choices=Station.choices, blank=True, default="")
    station_custom_name = models.CharField(max_length=120, blank=True, default="")
    note = models.CharField(max_length=2000, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_refuelings"
    )
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    paid_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    paid_by_label = models.CharField(max_length=150, blank=True, default="")
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-day_sequence", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["vehicle", "date", "day_sequence"],
                name="refueling_day_position",
                deferrable=models.Deferrable.DEFERRED,
            ),
            models.CheckConstraint(condition=Q(liters__gt=0), name="refueling_positive_liters"),
            models.CheckConstraint(condition=Q(total_amount__gte=0), name="refueling_nonnegative_total"),
            models.CheckConstraint(
                condition=Q(unit_price_entered__isnull=True) | Q(unit_price_entered__gte=0),
                name="refueling_nonnegative_price",
            ),
            models.CheckConstraint(
                condition=Q(odometer_km__isnull=True) | Q(odometer_km__gte=0, odometer_km__lte=99999999),
                name="refueling_odometer_range",
            ),
            models.CheckConstraint(condition=Q(day_sequence__gt=0), name="refueling_positive_sequence"),
            models.CheckConstraint(
                condition=Q(paid_by_user__isnull=True) | Q(paid_by_label=""), name="refueling_single_payer"
            ),
        ]
        indexes = [models.Index(fields=["vehicle", "date", "day_sequence"]), models.Index(fields=["date"])]


class OctetLength(Length):
    function = "OCTET_LENGTH"


models.BinaryField.register_lookup(OctetLength)


class ReceiptAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    refueling = models.OneToOneField(Refueling, on_delete=models.CASCADE, related_name="receipt")
    original_bytes = models.BinaryField()
    preview_bytes = models.BinaryField()
    content_type = models.CharField(max_length=10)
    size_bytes = models.PositiveIntegerField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    original_filename = models.CharField(max_length=150)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(original_bytes__length__lte=10 * 1024 * 1024, original_bytes__length__gt=0),
                name="receipt_original_limit",
            ),
            models.CheckConstraint(
                condition=Q(preview_bytes__length__lte=2 * 1024 * 1024, preview_bytes__length__gt=0),
                name="receipt_preview_limit",
            ),
            models.CheckConstraint(
                condition=Q(width__gt=0, height__gt=0, size_bytes__gt=0, size_bytes__lte=10 * 1024 * 1024),
                name="receipt_dimensions_size",
            ),
        ]


class RequestDeduplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    key = models.UUIDField()
    payload_hash = models.CharField(max_length=64)
    result_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "key"], name="refueling_request_key")]
