"""Krátká rodinná cesta sdílí autorizační a účetní pravidla plné aplikace."""

import hashlib
import json
import uuid
from types import SimpleNamespace

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import record
from apps.core.errors import Problem
from apps.extensions import ocr
from apps.extensions.integrations import reserve
from apps.extensions.models import IntegrationGate
from apps.refuelings import receipts
from apps.refuelings import services as fuel
from apps.refuelings.selectors import refueling_for
from apps.vehicles.selectors import vehicle_for, vehicles_for
from apps.vehicles.services import lock_users, lock_vehicle

from .models import FamilyPreference, ReceiptDraft


def draft_tag(draft):
    return f'"receipt-draft:{draft.pk}:{draft.version}"'


def draft_for(request, draft_id):
    draft = get_object_or_404(ReceiptDraft, pk=draft_id, user=request.user)
    vehicle_for(request.user, draft.vehicle_id)
    return draft


def preference(user):
    item = FamilyPreference.objects.filter(user=user).first()
    vehicle_id = item.default_vehicle_id if item else None
    if vehicle_id and not vehicles_for(user).filter(pk=vehicle_id, status="ACTIVE").exists():
        vehicle_id = None
    return {
        "default_vehicle_id": str(vehicle_id) if vehicle_id else None
    }, f'"family:{user.pk}:{item.version if item else 0}"'


@transaction.atomic
def configure(request, user_id, vehicle_id):
    _, user = lock_users(request, user_id, admin=True)
    _, tag = preference(user)
    fuel.require_tag(request, tag)
    if vehicle_id:
        car = get_object_or_404(vehicles_for(user).select_for_update(), pk=vehicle_id, status="ACTIVE")
        fuel.authorize(user, car, "create")
    else:
        car = None
    item = FamilyPreference.objects.filter(user=user).first() or FamilyPreference(user=user)
    item.default_vehicle = car
    if item.pk:
        item.version += 1
    item.save()
    record(
        request, "family.configured", user, {"default_vehicle_id": str(vehicle_id) if vehicle_id else None}
    )
    return preference(user)


@transaction.atomic
def upload(request, vehicle_id, payload):
    lock_users(request)
    car = lock_vehicle(request, vehicle_id, manage=False)
    fuel.authorize(request.user, car, "create")
    try:
        key = uuid.UUID(request.headers.get("Idempotency-Key", ""))
    except (ValueError, TypeError) as error:
        raise ValidationError("Vyžadováno UUID Idempotency-Key.") from error
    previous = ReceiptDraft.objects.filter(user=request.user, upload_key=key).first()
    if previous:
        if previous.vehicle_id != car.pk or previous.metadata["sha256"] != payload["sha256"]:
            raise Problem("idempotency_conflict", "Tento požadavek již patří jiné účtence.", 409)
        return previous
    draft = ReceiptDraft.objects.create(
        user=request.user,
        vehicle=car,
        upload_key=key,
        original=payload["original_bytes"],
        preview=payload["preview_bytes"],
        metadata={
            key: value for key, value in payload.items() if key not in ["original_bytes", "preview_bytes"]
        },
    )
    record(request, "receipt.draft_created", draft, vehicle_id=car.pk)
    return draft


def recognize(request, draft_id):
    draft = draft_for(request, draft_id)
    fuel.authorize(request.user, vehicle_for(request.user, draft.vehicle_id), "create")
    fuel.require_tag(request, draft_tag(draft))
    if draft.result_id:
        raise Problem("draft_completed", "Účtenka už je uložená v historii.", 409)
    reserve(request, "ocr", 3, 20)
    slot, lease = ocr.acquire()
    try:
        raw, suggestions = ocr.engine(bytes(draft.original))
    finally:
        IntegrationGate.objects.filter(pk=slot, window=lease).update(window=timezone.now())
    with transaction.atomic():
        lock_users(request)
        car = lock_vehicle(request, draft.vehicle_id, manage=False)
        fuel.authorize(request.user, car, "create")
        current = ReceiptDraft.objects.select_for_update().get(pk=draft.pk, user=request.user)
        fuel.require_tag(request, draft_tag(current))
        if current.result_id:
            raise Problem("draft_completed", "Účtenka už je uložená v historii.", 409)
        current.raw_text, current.suggestions = raw, suggestions
        current.version += 1
        current.save(update_fields=["raw_text", "suggestions", "version"])
        record(request, "receipt.draft_recognized", current, vehicle_id=car.pk)
        return current


@transaction.atomic
def complete(request, draft_id, data):
    lock_users(request)
    initial = draft_for(request, draft_id)
    car = lock_vehicle(request, initial.vehicle_id, manage=False)
    draft = ReceiptDraft.objects.select_for_update().get(pk=initial.pk, user=request.user)
    if data["vehicle_id"] != car.pk:
        raise ValidationError({"vehicle_id": "Návrh účtenky patří jinému autu."})
    digest = hashlib.sha256(
        json.dumps(
            {k: v for k, v in data.items() if k != "confirmed_warning_codes"}, sort_keys=True, default=str
        ).encode()
    ).hexdigest()
    if draft.result_id:
        if digest != draft.completion_hash:
            raise Problem("idempotency_conflict", "Účtenka již byla uložená s jinými údaji.", 409)
        return refueling_for(request.user, draft.result_id)
    fuel.require_tag(request, draft_tag(draft))
    fuel.authorize(request.user, car, "create")
    child = SimpleNamespace(
        user=request.user,
        session=request.session,
        headers={"Idempotency-Key": str(draft.pk)},
        request_id=getattr(request, "request_id", ""),
    )
    item, _ = fuel.create(child, data)
    child.headers["If-Match"] = fuel.etag(item)
    receipts.save(
        child,
        item.pk,
        {**draft.metadata, "original_bytes": bytes(draft.original), "preview_bytes": bytes(draft.preview)},
    )
    draft.result_id, draft.completion_hash = item.pk, digest
    draft.version += 1
    draft.save(update_fields=["result_id", "completion_hash", "version"])
    record(request, "receipt.draft_completed", draft, vehicle_id=car.pk)
    return refueling_for(request.user, item.pk)
