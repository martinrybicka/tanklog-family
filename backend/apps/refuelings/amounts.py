from decimal import ROUND_HALF_UP, Decimal

from rest_framework.exceptions import ValidationError


def resolve_amount(values, previous=None):
    if "total_amount" in values and values["total_amount"] is not None:
        return values["total_amount"], "ENTERED"
    if previous and previous["amount_source"] == "ENTERED":
        return previous["total_amount"], "ENTERED"
    price = values.get("unit_price_entered")
    if price is None:
        raise ValidationError({"total_amount": "Zadejte částku nebo cenu za litr."})
    total = (values["liters"] * price).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    if total == 0:
        raise ValidationError(
            {"total_amount": "Pro nulovou částku zadejte výslovně nulu a potvrďte varování."}
        )
    return total, "CALCULATED"
