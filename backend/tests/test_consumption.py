"""Ručně stanovená očekávání C01–C34; testy vznikly před výpočetní službou."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.analytics.consumption import (
    Context,
    Record,
    aggregate_groups,
    aggregate_intervals,
    aggregate_purchases,
    build_intervals,
    compare_standard,
)
from apps.refuelings.amounts import resolve_amount

D = Decimal
START = date(2026, 1, 1)
END = date(2026, 12, 31)
CTX = Context("car", "PETROL", 0, "SINGLE_TANK", D("6"), "WLTP", "Výrobce", "")


def r(index, km, liters, full=True, amount=None, **kwargs):
    return Record(
        str(index),
        START + timedelta(days=index),
        1,
        D(str(liters)),
        D(str(amount)) if amount is not None else D(str(liters)) * 40,
        "PETROL",
        km,
        full,
        False,
        **kwargs,
    )


def baseline():
    return (r(0, 10000, 50), r(1, 10300, 20, False), r(2, 10600, 25))


def result(records=None, ctx=CTX):
    return build_intervals(ctx, baseline() if records is None else tuple(records))


def totals(value, start=START, end=END):
    return aggregate_intervals(value.intervals, start, end)


def q(value):
    return None if value is None else value.quantize(D(".000001"))


def test_C01_empty():
    value = result([])
    assert value.status == "INSUFFICIENT_DATA" and not value.intervals and totals(value).consumption is None


def test_C02_single_anchor():
    assert totals(result([r(0, 10000, 50)])).consumption is None


def test_C03_no_full_boundaries():
    assert "MISSING_ANCHOR" in result([r(0, 10000, 20, False), r(1, 10400, 30, False)]).reasons


def test_C04_anchor_purchase_is_excluded():
    t = totals(result([r(0, 10000, 50), r(1, 10600, 45)]))
    assert t.liters == 45 and t.distance_km == 600 and q(t.consumption) == D("7.500000")


def test_C05_partial_fuel_counts():
    value = result()
    assert q(totals(value).consumption) == D("7.500000")
    assert tuple(row.id for row in value.intervals[0].records) == ("0", "1", "2")


def test_C06_missing_partial_odometer_keeps_fuel():
    rows = list(baseline())
    rows[1] = replace(rows[1], odometer_km=None)
    value = result(rows)
    assert q(totals(value).consumption) == D("7.500000") and ("1", "MISSING_ODOMETER") in value.warnings


def test_C07_full_without_odometer_is_not_boundary():
    rows = list(baseline())
    rows[1] = replace(rows[1], odometer_km=None, is_full_tank=True)
    value = result(rows)
    assert len(value.intervals) == 1 and totals(value).liters == 45


def test_C08_missing_first_full_odometer():
    assert totals(result([r(0, None, 50), r(1, 10600, 25)])).consumption is None


def test_C09_open_interval():
    value = result(baseline()[:2])
    assert "OPEN_INTERVAL" in value.reasons and totals(value).consumption is None
    assert aggregate_purchases(value.records, START, END).liters == 70


def test_C10_zero_distance_then_valid():
    value = result([r(0, 10000, 50), r(1, 10000, 20), r(2, 10500, 40)])
    assert "ZERO_DISTANCE" in value.intervals[0].reasons and q(totals(value).consumption) == D("8.000000")


def test_C11_decrease_blocks_recovery():
    value = result([r(0, 10000, 50), r(1, 10500, 20, False), r(2, 10400, 25), r(3, 11000, 40)])
    assert totals(value).consumption is None and value.status == "INVALID_DATA"
    assert all("ODOMETER_DECREASE" in i.reasons for i in value.intervals)


def test_C12_below_initial_blocks_all():
    value = result([r(0, 9900, 40), r(1, 10500, 40)], replace(CTX, initial_odometer_km=10000))
    assert totals(value).consumption is None and "BELOW_INITIAL_ODOMETER" in value.reasons


def test_C13_weighted_not_arithmetic():
    assert q(totals(result([r(0, 0, 40), r(1, 500, 50), r(2, 1500, 30)])).consumption) == D("5.333333")


def test_C14_same_day_explicit_order():
    rows = [replace(row, date=START, day_sequence=i + 1) for i, row in enumerate(baseline())]
    assert q(totals(result(rows)).consumption) == D("7.500000")


def test_C15_same_day_swapped_end_invalidates_closed_interval():
    a, p, b = baseline()
    rows = [
        replace(a, date=START, day_sequence=1),
        replace(b, date=START, day_sequence=2),
        replace(p, date=START, day_sequence=3),
    ]
    assert totals(result(rows)).consumption is None


def test_C16_backdated_insertion_recomputes():
    a, p, b = baseline()
    extra = replace(r(3, 10400, 5, False), date=p.date, day_sequence=2)
    assert q(totals(result([a, p, extra, b])).consumption) == D("8.333333")


def test_C17_edit_recomputes():
    a, p, b = baseline()
    assert q(totals(result([a, replace(p, liters=D(15)), b])).consumption) == D("6.666667")


def test_C18_delete_recomputes_without_inventing_fuel():
    a, _, b = baseline()
    assert q(totals(result([a, b])).consumption) == D("4.166667")


def february_rows():
    return tuple(
        replace(row, date=day)
        for row, day in zip(baseline(), [date(2026, 1, 31), date(2026, 2, 1), date(2026, 2, 5)], strict=True)
    )


def test_C19_filter_uses_ending_day_and_keeps_anchor():
    rows = february_rows()
    t = totals(result(rows), date(2026, 2, 1), date(2026, 2, 28))
    assert (
        q(t.consumption) == D("7.500000")
        and aggregate_purchases(rows, date(2026, 2, 1), date(2026, 2, 28)).liters == 45
    )


def test_C20_purchase_day_without_closed_interval():
    rows = february_rows()
    day = date(2026, 2, 1)
    assert (
        totals(result(rows), day, day).consumption is None
        and aggregate_purchases(rows, day, day).liters == 20
    )


def test_C21_interval_cost_is_not_all_purchase_cost():
    rows = [r(0, 0, 40, amount=1600), r(1, 300, 20, False, 780), r(2, 600, 25, amount=1000)]
    t = totals(result(rows))
    assert t.amount == 1780 and q(t.cost_per_100km) == D("296.666667")
    assert aggregate_purchases(rows, START, END).amount == 3380


def test_C22_weighted_purchase_price():
    value = aggregate_purchases([r(0, None, 10, amount=400), r(1, None, 30, amount=1080)], START, END)
    assert q(value.unit_price) == D("37.000000")


def test_C23_half_up_and_entered_amount():
    assert resolve_amount({"liters": D("12.345"), "unit_price_entered": D("38.90")}) == (
        D("480.22"),
        "CALCULATED",
    )
    assert resolve_amount(
        {"liters": D("12.345"), "unit_price_entered": D("38.90"), "total_amount": D("480.00")}
    ) == (D("480.00"), "ENTERED")


def test_C24_gap_then_new_valid_interval():
    a, p, b = baseline()
    value = result([a, replace(p, break_before=True), b, r(3, 11200, 42)])
    assert "HISTORY_GAP" in value.intervals[0].reasons and q(totals(value).consumption) == D("7.000000")


def test_C25_mixed_fuel():
    a, p, b = baseline()
    value = result([a, replace(p, fuel_type="DIESEL"), b])
    assert "MIXED_FUEL" in value.intervals[0].reasons and totals(value).consumption is None
    assert aggregate_purchases(value.records, START, END).liters == 95


def test_C26_multiple_tanks_unsupported():
    value = result(ctx=replace(CTX, consumption_mode="UNSUPPORTED_MULTI_TANK"))
    assert value.status == "UNSUPPORTED" and totals(value).consumption is None
    assert aggregate_purchases(value.records, START, END).liters == 95


def test_C27_redundant_vehicle_is_not_counted_twice():
    value = result()
    groups = aggregate_groups([value, value], START, END)
    assert len(groups) == 1 and groups[0].totals.liters == 45


def test_C28_same_fuel_across_vehicles_weighted():
    other = result([r(0, 0, 50), r(1, 500, 35)], replace(CTX, vehicle_id="other"))
    assert q(aggregate_groups([result(), other], START, END)[0].totals.consumption) == D("7.272727")


def test_C29_different_fuels_have_separate_groups():
    ctx = replace(CTX, vehicle_id="other", fuel_type="DIESEL")
    other = result(
        [replace(r(0, 0, 50), fuel_type="DIESEL"), replace(r(1, 500, 35), fuel_type="DIESEL")], ctx
    )
    groups = aggregate_groups([result(), other], START, END)
    assert {g.fuel_type: q(g.totals.consumption) for g in groups} == {
        "PETROL": D("7.500000"),
        "DIESEL": D("7.000000"),
    }


def test_C30_late_decrease_keeps_only_older_unaffected_interval():
    value = result([r(0, 0, 40), r(1, 500, 50), r(2, 1000, 40), r(3, 900, 10, False), r(4, 1500, 30)])
    assert totals(value).valid_count == 1 and q(totals(value).consumption) == D("10.000000")
    assert not value.intervals[0].reasons and all(
        "ODOMETER_DECREASE" in i.reasons for i in value.intervals[1:]
    )


def test_C31_invalid_domain_values_rejected():
    for changes in [
        {"liters": D(0)},
        {"liters": D(-1)},
        {"liters": D("1.0001")},
        {"liters": D("NaN")},
        {"liters": D("Infinity")},
        {"odometer_km": -1},
    ]:
        with pytest.raises(ValueError):
            result([replace(r(0, 0, 40), **changes)])


def test_C32_duplicate_day_positions_are_invalid():
    value = result([replace(r(0, 0, 40), date=START), replace(r(1, 600, 45), date=START)])
    assert value.status == "INVALID_DATA" and "INVALID_ORDER" in value.reasons and not value.intervals


def test_C33_standard_comparison():
    comparison = compare_standard(CTX, totals(result()))
    assert comparison.difference == D("1.5") and comparison.percent == D("25")


def test_C34_unknown_or_zero_standard_or_no_measurement():
    assert compare_standard(replace(CTX, standard_consumption=None), totals(result())) is None
    assert compare_standard(replace(CTX, standard_consumption=D(0)), totals(result())) is None
    assert compare_standard(CTX, totals(result([]))) is None


def test_inputs_are_immutable_and_deterministic():
    rows = baseline()
    assert result(rows) == result(rows)
    assert rows == baseline()
    with pytest.raises((AttributeError, TypeError)):
        rows[0].liters = D(1)
