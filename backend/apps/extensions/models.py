import uuid

from django.conf import settings
from django.db import models

from apps.vehicles.models import Vehicle


class VehicleEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(
        max_length=12,
        choices=[(v, v) for v in ["SERVICE", "INSPECTION", "INSURANCE", "REMINDER", "ENERGY"]],
    )
    title = models.CharField(max_length=150)
    date = models.DateField()
    note = models.CharField(max_length=2000, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    odometer_km = models.PositiveIntegerField(null=True)
    due_date = models.DateField(null=True)
    due_odometer_km = models.PositiveIntegerField(null=True)
    notice_days = models.PositiveSmallIntegerField(default=30)
    notice_km = models.PositiveIntegerField(default=1000)
    closed = models.BooleanField(default=False)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True)
    unit = models.CharField(max_length=3, blank=True, choices=[("kg", "kg"), ("kWh", "kWh")])
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="event_amount_nonnegative"),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        kind="ENERGY",
                        quantity__isnull=False,
                        quantity__gt=0,
                        unit__in=["kg", "kWh"],
                    )
                    | (~models.Q(kind="ENERGY") & models.Q(quantity__isnull=True, unit=""))
                ),
                name="event_quantity_unit",
            ),
        ]


class ExtensionRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    key = models.UUIDField()
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT)
    payload_hash = models.CharField(max_length=64)
    result_id = models.UUIDField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "key"], name="extension_request_unique")]


class ImportBatch(models.Model):
    vehicle_version = models.PositiveIntegerField()
    history_revision = models.PositiveBigIntegerField()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT)
    kind = models.CharField(max_length=10)
    raw = models.TextField()
    rows = models.JSONField(default=list)
    errors = models.JSONField(default=list)
    warnings = models.JSONField(default=list)
    results = models.JSONField(default=list)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class IntegrationGate(models.Model):
    name = models.CharField(max_length=80, unique=True)
    window = models.DateTimeField()
    used = models.PositiveIntegerField(default=0)


class IntegrationAttempt(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    provider = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class VehicleDataSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, null=True)
    vin = models.CharField(max_length=17)
    raw = models.JSONField()
    suggestions = models.JSONField(default=dict)
    applied_fields = models.JSONField(default=list)
    mapping_version = models.CharField(max_length=20, default="rsv-1")
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed = models.BooleanField(default=False)


class VehicleImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=10, default="CANDIDATE")
    original = models.BinaryField()
    preview = models.BinaryField()
    content_type = models.CharField(max_length=10)
    metadata = models.JSONField()
    match = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["vehicle"],
                condition=models.Q(status="ACTIVE"),
                name="one_active_vehicle_image",
            )
        ]


class ReceiptExtraction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    refueling = models.ForeignKey("refuelings.Refueling", on_delete=models.CASCADE)
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    receipt_hash = models.CharField(max_length=64)
    receipt_version = models.PositiveIntegerField()
    engine = models.CharField(max_length=80)
    raw_text = models.TextField()
    suggestions = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
