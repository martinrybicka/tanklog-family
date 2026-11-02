import hashlib
import re
import warnings
from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditEvent, record
from apps.core.errors import Problem
from apps.vehicles.services import lock_users

from .models import ReceiptAttachment
from .services import audit, authorize, bump, locked_item

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 24_000_000


def validate_image(upload):
    if upload.size > MAX_BYTES:
        raise Problem("file_too_large", "Účtenka smí mít nejvýše 10 MiB.", 413)
    original = upload.read(MAX_BYTES + 1)
    if not original or len(original) > MAX_BYTES:
        raise Problem("file_too_large", "Účtenka je prázdná nebo přesahuje 10 MiB.", 413)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(original)) as image:
                content_type = {"JPEG": "image/jpeg", "PNG": "image/png"}.get(image.format)
                if not content_type or content_type != upload.content_type:
                    raise ValidationError(
                        {"file": "Povoleny jsou pouze skutečné JPEG/PNG s odpovídajícím MIME typem."}
                    )
                if image.width * image.height > MAX_PIXELS or getattr(image, "n_frames", 1) != 1:
                    raise ValidationError(
                        {"file": "Obrázek smí mít nejvýše 24 megapixelů a nesmí být animovaný."}
                    )
                width, height = image.size
                image.verify()
            with Image.open(BytesIO(original)) as decoded:
                decoded.load()
                preview = ImageOps.exif_transpose(decoded).convert("RGBA")
                preview.thumbnail((1600, 1600))
                clean = Image.new("RGB", preview.size, "white")
                clean.paste(preview, mask=preview.getchannel("A"))
                output = BytesIO()
                clean.save(output, format="JPEG", quality=80, optimize=True)
                preview_bytes = output.getvalue()
                if len(preview_bytes) > 2 * 1024 * 1024:
                    raise ValidationError({"file": "Náhled přesahuje povolenou velikost."})
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise ValidationError({"file": "Obrázek je poškozený, nepodporovaný nebo příliš velký."}) from error
    name = upload.name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^\w .-]", "_", name, flags=re.UNICODE).strip(" .")[:140] or "uctenka"
    # Přípona odpovídá ověřenému obsahu, nikoli původní cestě klienta.
    name = name.rsplit(".", 1)[0] + (".jpg" if content_type == "image/jpeg" else ".png")
    return {
        "original_bytes": original,
        "preview_bytes": preview_bytes,
        "content_type": content_type,
        "size_bytes": len(original),
        "width": width,
        "height": height,
        "sha256": hashlib.sha256(original).hexdigest(),
        "original_filename": name,
    }


@transaction.atomic
def save(request, item_id, payload, replace=False):
    item, vehicle = locked_item(request, item_id)
    authorize(request.user, vehicle, "edit", item)
    existing = ReceiptAttachment.objects.filter(refueling=item).first()
    if existing and not replace:
        raise Problem("receipt_exists", "Účtenka už existuje. Pro náhradu použijte akci Nahradit.", 409)
    if replace and not existing:
        raise Problem("not_found", "Účtenka není dostupná.", 404)
    attachment = existing or ReceiptAttachment(refueling=item)
    for key, value in payload.items():
        setattr(attachment, key, value)
    attachment.uploaded_by = request.user
    if existing:
        attachment.version += 1
    attachment.save()
    item.version += 1
    item.updated_by = request.user
    item.save(update_fields=["version", "updated_by", "updated_at"])
    bump(vehicle)
    audit(
        request,
        "receipt.replaced" if existing else "receipt.created",
        item,
        {"receipt_id": str(attachment.pk), "sha256": attachment.sha256},
    )
    return item


@transaction.atomic
def delete(request, item_id):
    item, vehicle = locked_item(request, item_id)
    authorize(request.user, vehicle, "edit", item)
    attachment = ReceiptAttachment.objects.filter(refueling=item).first()
    if not attachment:
        raise Problem("not_found", "Účtenka není dostupná.", 404)
    audit(request, "receipt.deleted", item, {"receipt_id": str(attachment.pk)})
    attachment.delete()
    item.version += 1
    item.updated_by = request.user
    item.save(update_fields=["version", "updated_by", "updated_at"])
    bump(vehicle)
    return item


@transaction.atomic
def check_rate(request, item):
    lock_users(request)
    attempts = AuditEvent.objects.filter(
        actor=request.user,
        action="receipt.upload_attempt",
        occurred_at__gte=timezone.now() - timedelta(minutes=1),
    ).count()
    if attempts >= getattr(settings, "RECEIPT_UPLOADS_PER_MINUTE", 20):
        error = Problem("upload_limited", "Příliš mnoho uploadů. Zkuste to za minutu.", 429)
        error.wait = 60
        raise error
    record(request, "receipt.upload_attempt", item, vehicle_id=item.vehicle_id)
