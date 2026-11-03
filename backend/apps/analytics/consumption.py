"""Čistá metodika plná–plná. Bez HTTP, ORM, sessions a zaokrouhlování mezivýsledků."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

ZERO = Decimal(0)
FUELS = {"PETROL", "DIESEL", "LPG", "ETHANOL", "OTHER_LIQUID"}


@dataclass(frozen=True)
class Context:
    vehicle_id: str
    fuel_type: str
    initial_odometer_km: int
    consumption_mode: str
    standard_consumption: Decimal | None = None
    standard_methodology: str = "UNKNOWN"
    standard_source: str = ""
    standard_source_note: str = ""


@dataclass(frozen=True)
class Record:
    id: str
    date: date
    day_sequence: int
    liters: Decimal
    total_amount: Decimal
    fuel_type: str
    odometer_km: int | None
    is_full_tank: bool
    break_before: bool

    def __post_init__(self):
        for value, places, maximum, positive in [
            (self.liters, 3, Decimal("9999999.999"), True),
            (self.total_amount, 2, Decimal("999999999999.99"), False),
        ]:
            if (
                not isinstance(value, Decimal)
                or not value.is_finite()
                or value < 0
                or (positive and value == 0)
                or value > maximum
                or value != value.quantize(Decimal(1).scaleb(-places))
            ):
                raise ValueError("Neplatná přesnost nebo rozsah účetní hodnoty.")
        if type(self.odometer_km) not in [int, type(None)] or (
            self.odometer_km is not None and not 0 <= self.odometer_km <= 99999999
        ):
            raise ValueError("Neplatný tachometr.")
        if (
            type(self.date) is not date
            or type(self.day_sequence) is not int
            or self.day_sequence < 1
            or self.fuel_type not in FUELS
            or type(self.is_full_tank) is not bool
            or type(self.break_before) is not bool
        ):
            raise ValueError("Neplatný typ nebo pořadí záznamu.")


@dataclass(frozen=True)
class Interval:
    vehicle_id: str
    records: tuple[Record, ...]
    liters: Decimal
    amount: Decimal
    distance_km: int
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def start(self):
        return self.records[0]

    @property
    def end(self):
        return self.records[-1]

    @property
    def fuel_type(self):
        return self.start.fuel_type

    @property
    def valid(self):
        return not self.reasons

    @property
    def consumption(self):
        return self.liters / self.distance_km * 100 if self.valid else None

    @property
    def cost_per_100km(self):
        return self.amount / self.distance_km * 100 if self.valid else None


@dataclass(frozen=True)
class BuildResult:
    context: Context
    records: tuple[Record, ...]
    intervals: tuple[Interval, ...]
    status: str
    reasons: tuple[str, ...]
    warnings: tuple[tuple[str, str], ...]
    open_records: tuple[Record, ...]


@dataclass(frozen=True)
class Totals:
    liters: Decimal = ZERO
    amount: Decimal = ZERO
    distance_km: int = 0
    valid_count: int = 0
    excluded_count: int = 0

    @property
    def consumption(self):
        return self.liters / self.distance_km * 100 if self.distance_km else None

    @property
    def cost_per_100km(self):
        return self.amount / self.distance_km * 100 if self.distance_km else None


@dataclass(frozen=True)
class Purchases:
    liters: Decimal
    amount: Decimal
    count: int

    @property
    def unit_price(self):
        return self.amount / self.liters if self.liters else None


@dataclass(frozen=True)
class FuelGroup:
    fuel_type: str
    totals: Totals


@dataclass(frozen=True)
class Comparison:
    standard: Decimal
    difference: Decimal
    percent: Decimal
    methodology: str
    source: str
    source_note: str


def build_intervals(context, ordered_records):
    records = tuple(ordered_records)
    if type(context.initial_odometer_km) is not int or not 0 <= context.initial_odometer_km <= 99999999:
        raise ValueError("Neplatný počáteční tachometr.")
    positions = tuple((r.date, r.day_sequence) for r in records)
    warnings = tuple((r.id, "MISSING_ODOMETER") for r in records if r.odometer_km is None)
    if (
        positions != tuple(sorted(positions))
        or len(set(positions)) != len(positions)
        or len({r.id for r in records}) != len(records)
    ):
        return BuildResult(context, records, (), "INVALID_DATA", ("INVALID_ORDER",), warnings, ())
    anchors = [i for i, r in enumerate(records) if r.is_full_tank and r.odometer_km is not None]
    below_initial = any(
        r.odometer_km is not None and r.odometer_km < context.initial_odometer_km for r in records
    )
    blocked_from = None
    previous = None
    for i, r in enumerate(records):
        if r.odometer_km is None:
            continue
        if previous is not None and r.odometer_km < records[previous].odometer_km:
            earlier = [a for a in anchors if a < previous]
            blocked_from = earlier[-1] if earlier else -1
            break
        previous = i
    unsupported = context.consumption_mode != "SINGLE_TANK"
    unsupported_reason = "UNSUPPORTED_UNIT" if context.fuel_type not in FUELS else "UNSUPPORTED_MULTI_TANK"
    intervals = []
    for start, end in zip(anchors, anchors[1:]):
        subset = records[start : end + 1]
        distance = subset[-1].odometer_km - subset[0].odometer_km
        reasons = []
        if distance <= 0:
            reasons.append("ZERO_DISTANCE")
        if blocked_from is not None and start >= blocked_from:
            reasons.append("ODOMETER_DECREASE")
        if below_initial:
            reasons.append("BELOW_INITIAL_ODOMETER")
        if any(row.break_before for row in subset[1:]):
            reasons.append("HISTORY_GAP")
        if len({row.fuel_type for row in subset}) > 1:
            reasons.append("MIXED_FUEL")
        if unsupported:
            reasons.append(unsupported_reason)
        intervals.append(
            Interval(
                context.vehicle_id,
                subset,
                sum((row.liters for row in subset[1:]), ZERO),
                sum((row.total_amount for row in subset[1:]), ZERO),
                distance,
                tuple(reasons),
                ("MISSING_ODOMETER",) if any(row.odometer_km is None for row in subset) else (),
            )
        )
    reasons = set(reason for interval in intervals for reason in interval.reasons)
    if below_initial:
        reasons.add("BELOW_INITIAL_ODOMETER")
    if blocked_from is not None:
        reasons.add("ODOMETER_DECREASE")
    if unsupported:
        reasons.add(unsupported_reason)
    if not anchors or anchors[0] > 0:
        reasons.add("MISSING_ANCHOR")
    open_records = records[anchors[-1] :] if anchors and anchors[-1] < len(records) - 1 else ()
    if open_records:
        reasons.add("OPEN_INTERVAL")
    if unsupported:
        status = "UNSUPPORTED"
    elif any(interval.valid for interval in intervals):
        status = "VALID"
    elif intervals or below_initial or blocked_from is not None:
        status = "INVALID_DATA"
    else:
        status = "INSUFFICIENT_DATA"
    return BuildResult(
        context,
        records,
        tuple(intervals),
        status,
        tuple(sorted(reasons)),
        warnings,
        open_records,
    )


def aggregate_intervals(intervals, start, end):
    selected = [i for i in intervals if start <= i.end.date <= end]
    valid = [i for i in selected if i.valid]
    return Totals(
        sum((i.liters for i in valid), ZERO),
        sum((i.amount for i in valid), ZERO),
        sum(i.distance_km for i in valid),
        len(valid),
        len(selected) - len(valid),
    )


def aggregate_purchases(records, start, end):
    selected = [r for r in records if start <= r.date <= end]
    return Purchases(
        sum((r.liters for r in selected), ZERO),
        sum((r.total_amount for r in selected), ZERO),
        len(selected),
    )


def aggregate_groups(results, start, end):
    unique = {value.context.vehicle_id: value for value in results}
    fuels = {i.fuel_type for value in unique.values() for i in value.intervals if start <= i.end.date <= end}
    fuels |= {value.context.fuel_type for value in unique.values() if not value.intervals}
    return tuple(
        FuelGroup(
            fuel,
            aggregate_intervals(
                [i for value in unique.values() for i in value.intervals if i.fuel_type == fuel],
                start,
                end,
            ),
        )
        for fuel in sorted(fuels)
    )


def compare_standard(context, totals):
    standard = context.standard_consumption
    if standard is None or standard <= 0 or totals.consumption is None:
        return None
    return Comparison(
        standard,
        totals.consumption - standard,
        (totals.consumption / standard - 1) * 100,
        context.standard_methodology,
        context.standard_source,
        context.standard_source_note,
    )
