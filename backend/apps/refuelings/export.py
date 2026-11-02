from io import BytesIO

from django.conf import settings
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from apps.core.errors import Problem

from .selectors import filtered

HEADERS = [
    "Datum",
    "Pořadí dne",
    "Vozidlo",
    "Palivo",
    "Litry",
    "Cena za litr (Kč)",
    "Celkem (Kč)",
    "Tachometr (km)",
    "Plná nádrž",
    "Mezera v evidenci",
    "Stanice",
    "Poznámka",
    "Autor",
    "Plátce",
    "Zdroj částky",
]


def export_xlsx(user, params):
    query = filtered(user, params)
    limit = getattr(settings, "REFUELING_EXPORT_LIMIT", 50000)
    # Jeden omezený SQL dotaz poskytne konzistentní výběr i hodnoty, bez obrázků.
    rows = list(
        query.values(
            "date",
            "day_sequence",
            "vehicle__name",
            "fuel_type",
            "liters",
            "unit_price_entered",
            "total_amount",
            "odometer_km",
            "is_full_tank",
            "break_before",
            "station_code",
            "station_custom_name",
            "note",
            "created_by__display_name",
            "created_by__username",
            "paid_by_user__display_name",
            "paid_by_user__username",
            "paid_by_label",
            "amount_source",
        )[: limit + 1]
    )
    if len(rows) > limit:
        raise Problem("export_limit", f"Export má limit {limit} řádků. Zužte filtry.", 400)
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Tankování")
    sheet.freeze_panes = "A2"
    sheet.append(HEADERS)
    for row in rows:
        values = [
            row["date"],
            row["day_sequence"],
            row["vehicle__name"],
            row["fuel_type"],
            row["liters"],
            row["unit_price_entered"],
            row["total_amount"],
            row["odometer_km"],
            "Ano" if row["is_full_tank"] else "Ne",
            "Ano" if row["break_before"] else "Ne",
            row["station_custom_name"] or row["station_code"],
            row["note"],
            row["created_by__display_name"] or row["created_by__username"],
            row["paid_by_label"] or row["paid_by_user__display_name"] or row["paid_by_user__username"] or "",
            "Zadaná" if row["amount_source"] == "ENTERED" else "Vypočtená",
        ]
        cells = []
        for index, value in enumerate(values):
            if isinstance(value, str):
                value = ILLEGAL_CHARACTERS_RE.sub("", value)
            cell = WriteOnlyCell(sheet, value=value)
            if isinstance(value, str):
                cell.data_type = "s"
            if index == 0:
                cell.number_format = "dd.mm.yyyy"
            elif index == 4:
                cell.number_format = "#,##0.000"
            elif index == 5:
                cell.number_format = "#,##0.0000"
            elif index == 6:
                cell.number_format = '#,##0.00" Kč"'
            cells.append(cell)
        sheet.append(cells)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
