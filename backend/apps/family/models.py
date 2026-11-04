import uuid

from django.conf import settings
from django.db import models


class FamilyPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    default_vehicle = models.ForeignKey("vehicles.Vehicle", null=True, on_delete=models.SET_NULL)
    version = models.PositiveIntegerField(default=1)


class ReceiptDraft(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    vehicle = models.ForeignKey("vehicles.Vehicle", on_delete=models.PROTECT)
    upload_key = models.UUIDField()
    original = models.BinaryField()
    preview = models.BinaryField()
    metadata = models.JSONField()
    suggestions = models.JSONField(default=dict)
    raw_text = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    result_id = models.UUIDField(null=True)
    completion_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "upload_key"], name="family_upload_key")]
