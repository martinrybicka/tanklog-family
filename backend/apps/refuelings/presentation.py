from decimal import ROUND_HALF_UP, Decimal

from .models import ReceiptAttachment
from .quality import warnings_for
from .selectors import rights


def present(request, item, vehicle):
    fields = [
        "id",
        "vehicle_id",
        "date",
        "day_sequence",
        "liters",
        "unit_price_entered",
        "total_amount",
        "amount_source",
        "odometer_km",
        "is_full_tank",
        "break_before",
        "fuel_type",
        "station_code",
        "station_custom_name",
        "note",
        "created_by_id",
        "updated_by_id",
        "paid_by_user_id",
        "paid_by_label",
        "version",
        "created_at",
        "updated_at",
    ]
    data = {key: getattr(item, key) for key in fields}
    data.update(
        vehicle_name=item.vehicle.name,
        created_by_name=item.created_by.display_name or item.created_by.username,
        updated_by_name=item.updated_by.display_name or item.updated_by.username,
        paid_by_name=(item.paid_by_user.display_name or item.paid_by_user.username)
        if item.paid_by_user
        else item.paid_by_label,
    )
    data["effective_unit_price"] = str(
        (item.total_amount / item.liters).quantize(Decimal(".0001"), rounding=ROUND_HALF_UP)
    )
    for key, value in data.items():
        if isinstance(value, Decimal):
            data[key] = str(value)
    data["permissions"] = rights(request.user, vehicle, item)
    data["history_revision"] = vehicle.history_revision
    data["quality_warnings"] = warnings_for(
        vehicle,
        {
            key: getattr(item, key)
            for key in [
                "date",
                "day_sequence",
                "fuel_type",
                "unit_price_entered",
                "liters",
                "total_amount",
                "odometer_km",
            ]
        },
        item,
    )
    data["receipt"] = (
        ReceiptAttachment.objects.filter(refueling=item)
        .values("id", "content_type", "size_bytes", "width", "height", "original_filename", "version")
        .first()
    )
    return data
