from decimal import ROUND_HALF_UP, Decimal

from .models import Refueling

MESSAGES = {
    "fuel_mismatch": "Palivo se liší od primárního paliva vozidla.",
    "amount_difference": "Přesná částka se liší od součinu litrů a ceny. Zachováme zadanou částku.",
    "tank_capacity_exceeded": "Množství přesahuje uvedený objem nádrže.",
    "missing_odometer": "Chybí tachometr. Záznam uložíme, ale údaj může chybět pro měření spotřeby.",
    "odometer_below_initial": "Tachometr je nižší než počáteční stav vozidla.",
    "odometer_decrease": "Tachometr neodpovídá sousedním záznamům. Budoucí měření může být neplatné.",
    "similar_record": "V tomto dni už existuje podobné tankování.",
    "day_order": "Ve stejném dni je další tankování. Potvrďte zvolenou pozici v pořadí.",
    "zero_amount": "Částka je výslovně nulová. Potvrďte bezplatné tankování.",
}


def warnings_for(vehicle, values, item=None):
    codes = []

    def add(code):
        if code not in codes:
            codes.append(code)

    if values["fuel_type"] != vehicle.fuel_type:
        add("fuel_mismatch")
    price = values.get("unit_price_entered")
    if (
        price is not None
        and (values["liters"] * price).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        != values["total_amount"]
    ):
        add("amount_difference")
    if vehicle.tank_capacity_l and values["liters"] > vehicle.tank_capacity_l:
        add("tank_capacity_exceeded")
    if values["total_amount"] == 0:
        add("zero_amount")
    km = values.get("odometer_km")
    if km is None:
        add("missing_odometer")
    elif km < vehicle.initial_odometer_km:
        add("odometer_below_initial")
    history = list(
        Refueling.objects.filter(vehicle=vehicle)
        .exclude(pk=item.pk if item else None)
        .order_by("date", "day_sequence")
        .values("date", "day_sequence", "odometer_km", "liters", "total_amount")
    )
    same_day = [row for row in history if row["date"] == values["date"]]
    if same_day:
        add("day_order")
    if any(
        row["liters"] == values["liters"] and row["total_amount"] == values["total_amount"]
        for row in same_day
    ):
        add("similar_record")
    if km is not None:
        # Vyhodnotit zamýšlené pořadí po vložení/přesunu, nikoli původní čísla ostatních.
        position = values["day_sequence"] - 1
        previous = [
            row["odometer_km"]
            for row in history
            if row["date"] < values["date"] and row["odometer_km"] is not None
        ]
        previous += [row["odometer_km"] for row in same_day[:position] if row["odometer_km"] is not None]
        following = [row["odometer_km"] for row in same_day[position:] if row["odometer_km"] is not None]
        following += [
            row["odometer_km"]
            for row in history
            if row["date"] > values["date"] and row["odometer_km"] is not None
        ]
        if (previous and previous[-1] > km) or (following and following[0] < km):
            add("odometer_decrease")
    return [{"code": code, "message": MESSAGES[code]} for code in codes]
