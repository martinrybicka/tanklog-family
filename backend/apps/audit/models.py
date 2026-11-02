import uuid

from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=60)
    entity_type = models.CharField(max_length=40, default="user")
    entity_id = models.UUIDField(null=True)
    request_id = models.CharField(max_length=36, blank=True)
    changes = models.JSONField(default=dict)

    class Meta:
        ordering = ["-occurred_at", "-id"]


def record(request, action, target=None, changes=None, actor=None):
    return AuditEvent.objects.create(
        actor=actor or (request.user if request.user.is_authenticated else None),
        action=action,
        entity_id=target.pk if target else None,
        request_id=getattr(request, "request_id", ""),
        changes=changes or {},
    )
