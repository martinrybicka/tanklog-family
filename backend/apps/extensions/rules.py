"""Čistá pravidla termínů a přesných součtů, bez HTTP nebo ORM."""

from decimal import Decimal


def reminder_state(today, due_date, due_km, reading, days, km):
    if (due_date and due_date < today) or (due_km is not None and reading is not None and reading >= due_km):
        return "OVERDUE"
    if (due_date and (due_date - today).days <= days) or (
        due_km is not None and reading is not None and reading + km >= due_km
    ):
        return "SOON"
    if due_km is not None and reading is None:
        return "UNKNOWN"
    return "LATER"


def energy_totals(rows):
    result = {}
    for unit, quantity, amount in rows:
        total = result.setdefault(unit, [Decimal(0), Decimal(0)])
        total[0] += quantity
        total[1] += amount
    return {
        unit: {"quantity": f"{values[0]:.3f}", "amount": f"{values[1]:.2f}"}
        for unit, values in result.items()
    }
