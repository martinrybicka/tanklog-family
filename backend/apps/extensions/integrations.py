import hashlib
import io
import warnings
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from PIL import Image, ImageOps

from apps.audit.models import record
from apps.core.errors import Problem
from apps.vehicles.selectors import effective_role, vehicle_for
from apps.vehicles.services import bump, lock_users, lock_vehicle, require_version

from . import providers
from .models import (
    IntegrationAttempt,
    IntegrationGate,
    VehicleDataSnapshot,
    VehicleImage,
)


@transaction.atomic
def reserve(request, provider, limit=5, global_limit=20):
    lock_users(request)
    now = timezone.now()
    gate, _ = IntegrationGate.objects.get_or_create(name=provider, defaults={"window": now})
    gate = IntegrationGate.objects.select_for_update().get(pk=gate.pk)
    if now - gate.window >= timedelta(minutes=1):
        gate.window = now
        gate.used = 0
    count = IntegrationAttempt.objects.filter(
        actor=request.user, provider=provider, created_at__gt=now - timedelta(minutes=1)
    ).count()
    global_count = IntegrationAttempt.objects.filter(
        provider=provider, created_at__gt=now - timedelta(minutes=1)
    ).count()
    if global_count >= global_limit or count >= limit:
        raise Problem("integration_limited", "Příliš mnoho požadavků. Zkuste to za minutu.", 429)
    gate.used += 1
    gate.save()
    IntegrationAttempt.objects.create(actor=request.user, provider=provider)


def manageable(request, vehicle_id=None):
    if vehicle_id:
        car = vehicle_for(request.user, vehicle_id)
        if effective_role(request.user, car) not in ["ADMIN", "OWNER"]:
            raise Problem("permission_denied", "Údaje mění pouze vlastník/správce.", 403)
        return car


def lookup(request, vin, vehicle_id=None):
    manageable(request, vehicle_id)
    reserve(request, "rsv")
    raw, suggestions = providers.rsv(vin)
    with transaction.atomic():
        lock_users(request)
        car = lock_vehicle(request, vehicle_id) if vehicle_id else None
        snapshot = VehicleDataSnapshot.objects.create(
            applicant=request.user,
            vehicle=car,
            vin=vin,
            raw=raw,
            suggestions=suggestions,
        )
        record(request, "vin.preview", snapshot, vehicle_id=vehicle_id)
        return snapshot


def confirm_lookup(request, car, snapshot_id, selected_fields):
    snapshot = get_object_or_404(
        VehicleDataSnapshot.objects.select_for_update(),
        pk=snapshot_id,
        applicant=request.user,
    )
    if (
        snapshot.vehicle_id not in [None, car.pk]
        or snapshot.vin != car.vin
        or snapshot.created_at < timezone.now() - timedelta(hours=24)
    ):
        raise Problem("stale_lookup", "Návrh VIN vypršel nebo nepatří tomuto autu.", 409)
    applied = []
    for name in dict.fromkeys(selected_fields):
        if name not in snapshot.suggestions:
            raise Problem("invalid_lookup_field", "Vybrané pole není součástí návrhu VIN.", 400)
        value = snapshot.suggestions[name]
        actual = getattr(car, name)
        if (
            Decimal(str(actual)) == Decimal(str(value))
            if name in ["power_kw", "engine_displacement_cc"] and actual is not None
            else actual == value
        ):
            applied.append(name)
    snapshot.vehicle = car
    snapshot.confirmed = True
    snapshot.applied_fields = applied
    snapshot.save()
    record(request, "vin.confirmed", snapshot, {"fields": applied}, vehicle_id=car.pk)


def image_payload(raw):
    if not raw or len(raw) > 5 * 1024**2:
        raise Problem("image_invalid", "Fotografie je příliš velká.", 502)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                content = {"JPEG": "image/jpeg", "PNG": "image/png"}.get(image.format)
                if (
                    not content
                    or image.width * image.height > 12_000_000
                    or getattr(image, "n_frames", 1) != 1
                ):
                    raise ValueError()
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((800, 600))
                output = io.BytesIO()
                image.save(output, "JPEG", quality=82)
                return raw, output.getvalue(), content
    except (
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise Problem("image_invalid", "Zdroj neposkytl platnou bezpečnou fotografii.", 502) from error


def photo_match(car):
    return {
        "make": car.make,
        "model": car.model,
        "vin_hash": hashlib.sha256((car.vin or "").encode()).hexdigest(),
    }


def search_photos(request, vehicle_id):
    car = manageable(request, vehicle_id)
    snapshot = (
        VehicleDataSnapshot.objects.filter(vehicle=car, confirmed=True, vin=car.vin)
        .order_by("-created_at")
        .first()
    )
    if not snapshot or not all(
        name in snapshot.applied_fields and snapshot.suggestions.get(name) == getattr(car, name)
        for name in ["make", "model"]
    ):
        raise Problem(
            "vin_confirmation_required",
            "Nejdříve potvrďte dohledanou značku/model podle VIN.",
            409,
        )
    match = photo_match(car)
    reserve(request, "commons", 5, 20)
    candidates = []
    for metadata in providers.commons(car.make, car.model):
        try:
            raw = providers.fetch(
                metadata["url"],
                {"User-Agent": settings.COMMONS_USER_AGENT},
                5 * 1024**2,
            )
            metadata["downloaded_sha256"] = hashlib.sha256(raw).hexdigest()
            candidates.append((metadata, image_payload(raw)))
        except Problem:
            continue
    with transaction.atomic():
        lock_users(request)
        current = lock_vehicle(request, vehicle_id)
        if photo_match(current) != match:
            raise Problem("stale_version", "Údaje auta se změnily. Hledejte znovu.", 412)
        VehicleImage.objects.filter(vehicle=current, status="CANDIDATE").delete()
        result = []
        for metadata, (raw, preview, mime) in candidates:
            image = VehicleImage.objects.create(
                vehicle=current,
                applicant=request.user,
                original=raw,
                preview=preview,
                content_type=mime,
                metadata=metadata,
                match=match,
            )
            result.append(image)
        return result


@transaction.atomic
def choose_photo(request, vehicle_id, image_id):
    lock_users(request)
    car = lock_vehicle(request, vehicle_id)
    require_version(request, car)
    image = get_object_or_404(
        VehicleImage.objects.select_for_update(),
        pk=image_id,
        vehicle=car,
        status="CANDIDATE",
    )
    if image.match != photo_match(car) or image.created_at < timezone.now() - timedelta(hours=24):
        raise Problem("stale_photo", "Návrh již neodpovídá aktuálním údajům auta.", 409)
    VehicleImage.objects.filter(vehicle=car, status="ACTIVE").delete()
    image.status = "ACTIVE"
    image.save(update_fields=["status"])
    bump(car)
    record(request, "vehicle.photo_selected", image, vehicle_id=car.pk)


def photo_for(request, image_id):
    image = get_object_or_404(VehicleImage, pk=image_id)
    car = vehicle_for(request.user, image.vehicle_id)
    if image.match != photo_match(car):
        raise Problem("not_found", "Fotografie již neodpovídá autu.", 404)
    if image.status != "ACTIVE" and (
        image.status != "CANDIDATE" or effective_role(request.user, car) not in ["ADMIN", "OWNER"]
    ):
        raise Problem("not_found", "Fotografie není dostupná.", 404)
    return image
