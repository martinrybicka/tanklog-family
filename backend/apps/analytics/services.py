from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import asdict
from decimal import ROUND_HALF_UP, Decimal

from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounts.services import check_session
from apps.core.errors import Problem
from apps.refuelings.models import Refueling
from apps.vehicles.selectors import vehicle_for, vehicles_for

from .consumption import (
    Context,
    Record,
    aggregate_groups,
    aggregate_intervals,
    aggregate_purchases,
    build_intervals,
    compare_standard,
)
from .periods import bucket, buckets, resolve_period

ASSIGNMENT = "Spotřebu řadíme podle dne koncového tankování. Interval může začínat před vybraným obdobím."


@contextmanager
def snapshot(request):
    # Auth middleware již doběhl v autocommitu; read-only snapshot začíná až zde.
    # Vnější transakce by po dřívějším dotazu nedovolila nastavit izolaci.
    if connection.in_atomic_block:
        raise RuntimeError("Statistiky vyžadují vlastní snapshot transakci, bez ATOMIC_REQUESTS.")
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        actor = User.objects.get(pk=request.user.pk)
        check_session(request, actor)
        if actor.must_change_password:
            raise Problem("password_change_required", "Nejdříve nastavte vlastní heslo.", 403)
        request.user = actor
        yield


def number(value, places=6):
    return (
        None
        if value is None
        else format(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP), "f")
    )


def period_data(period):
    return {
        "period": period.kind,
        "anchor_date": period.anchor,
        "date_from": period.start,
        "date_to": period.end,
        "timezone": "Europe/Prague",
        "group_by": period.group_by,
    }


def totals_data(totals):
    return {
        "liters": number(totals.liters, 3),
        "amount": number(totals.amount, 2),
        "distance_km": totals.distance_km,
        "valid_intervals": totals.valid_count,
        "excluded_intervals": totals.excluded_count,
        "consumption_l_100km": number(totals.consumption),
        "purchase_cost_czk_100km": number(totals.cost_per_100km),
    }


def record_data(record):
    result = asdict(record)
    result["liters"] = number(record.liters, 3)
    result["total_amount"] = number(record.total_amount, 2)
    return result


def interval_data(interval, period):
    return {
        "vehicle_id": interval.vehicle_id,
        "start_id": interval.start.id,
        "end_id": interval.end.id,
        "start_date": interval.start.date,
        "end_date": interval.end.date,
        "start_odometer_km": interval.start.odometer_km,
        "end_odometer_km": interval.end.odometer_km,
        "liters": number(interval.liters, 3),
        "amount": number(interval.amount, 2),
        "distance_km": interval.distance_km,
        "fuel_type": interval.fuel_type,
        "status": "VALID" if interval.valid else "INVALID_DATA",
        "reasons": interval.reasons,
        "warnings": interval.warnings,
        "consumption_l_100km": number(interval.consumption),
        "purchase_cost_czk_100km": number(interval.cost_per_100km),
        "crosses_period_start": interval.start.date < period.start,
        "assignment_rule": "end_refueling_date",
        "explanation": ASSIGNMENT,
        "record_ids": [r.id for r in interval.records],
    }


def load(request, params, vehicle_id=None):
    try:
        period = resolve_period(params, timezone.localdate())
        bucket_dates = buckets(period)
    except (ValueError, OverflowError) as error:
        raise ValidationError(str(error)) from error
    chosen = vehicle_id or params.get("vehicle_id")
    if vehicle_id and params.get("vehicle_id") and str(params["vehicle_id"]) != str(vehicle_id):
        raise ValidationError({"vehicle_id": "Vozidlo v URL a filtru se musí shodovat."})
    if chosen:
        vehicle_for(request.user, chosen)
    vehicles = list(vehicles_for(request.user).filter(pk=chosen) if chosen else vehicles_for(request.user))
    ids = {str(v.pk): v for v in vehicles}
    grouped = defaultdict(list)
    fields = [
        "id",
        "vehicle_id",
        "date",
        "day_sequence",
        "liters",
        "total_amount",
        "fuel_type",
        "odometer_km",
        "is_full_tank",
        "break_before",
    ]
    for row in (
        Refueling.objects.filter(vehicle_id__in=ids).order_by("date", "day_sequence", "id").values(*fields)
    ):
        vid = str(row.pop("vehicle_id"))
        row["id"] = str(row["id"])
        grouped[vid].append(Record(**row))
    results = []
    for vid, vehicle in ids.items():
        ctx = Context(
            vid,
            vehicle.fuel_type,
            vehicle.initial_odometer_km,
            vehicle.consumption_mode,
            vehicle.standard_consumption_l_100km,
            vehicle.standard_methodology,
            vehicle.standard_source,
            vehicle.standard_source_note,
        )
        results.append(build_intervals(ctx, tuple(grouped[vid])))
    return period, bucket_dates, ids, results


def dashboard(request, params, vehicle_id=None):
    with snapshot(request):
        period, dates, vehicles, results = load(request, params, vehicle_id)
        all_records = tuple(r for value in results for r in value.records)
        purchases = aggregate_purchases(all_records, period.start, period.end)
        groups = aggregate_groups(results, period.start, period.end)
        candidates = sorted(
            [i for value in results for i in value.intervals if period.start <= i.end.date <= period.end],
            key=lambda i: (i.end.date, i.end.day_sequence, i.vehicle_id),
        )
        totals = aggregate_intervals(candidates, period.start, period.end)
        valid = [i for i in candidates if i.valid]
        reasons = Counter(reason for i in candidates for reason in i.reasons)
        vehicle_info = []
        for value in results:
            selected = [i for i in candidates if i.vehicle_id == value.context.vehicle_id]
            t = aggregate_intervals(selected, period.start, period.end)
            state = (
                "UNSUPPORTED"
                if value.status == "UNSUPPORTED"
                else "VALID"
                if t.valid_count
                else "INVALID_DATA"
                if t.excluded_count or (not selected and value.status == "INVALID_DATA")
                else "INSUFFICIENT_DATA"
            )
            causes = set(reason for i in selected for reason in i.reasons)
            if not selected and value.status == "INVALID_DATA":
                causes.update(value.reasons)
            if state == "UNSUPPORTED":
                causes.add(
                    "UNSUPPORTED_UNIT"
                    if value.context.fuel_type in ["CNG", "ELECTRIC"]
                    else "UNSUPPORTED_MULTI_TANK"
                )
            if not selected:
                causes.add("NO_CLOSED_INTERVAL" if value.intervals else "MISSING_ANCHOR")
            if value.open_records and value.open_records[-1].date <= period.end:
                causes.add("OPEN_INTERVAL")
            vid = value.context.vehicle_id
            vehicle_info.append(
                {
                    "vehicle_id": vid,
                    "name": vehicles[vid].name,
                    "status": state,
                    "reasons": sorted(causes),
                    "history_revision": vehicles[vid].history_revision,
                    "missing_odometer_ids": [
                        row_id for row_id, reason in value.warnings if reason == "MISSING_ODOMETER"
                    ],
                    "open_record_ids": [r.id for r in value.open_records],
                    **totals_data(t),
                }
            )
        points = {day: [] for day in dates}
        for row in all_records:
            if period.start <= row.date <= period.end:
                points[bucket(row.date, period.group_by)].append(row)
        purchase_points = []
        for day, rows in points.items():
            totals_for_bucket = aggregate_purchases(rows, period.start, period.end)
            purchase_points.append(
                {
                    "date": day,
                    "amount": number(totals_for_bucket.amount, 2),
                    "liters": number(totals_for_bucket.liters, 3),
                    "count": totals_for_bucket.count,
                    "unit_price": number(totals_for_bucket.unit_price),
                }
            )
        comparison = None
        if (
            len(results) == 1
            and len(groups) == 1
            and groups[0].fuel_type == results[0].context.fuel_type
            and (vehicle_id or params.get("vehicle_id"))
        ):
            value = compare_standard(results[0].context, totals)
            if value:
                comparison = {
                    "standard": number(value.standard, 3),
                    "difference_l_100km": number(value.difference),
                    "difference_percent": number(value.percent),
                    "methodology": value.methodology,
                    "source": value.source,
                    "source_note": value.source_note,
                }
        recent = sorted(
            [
                (value.context.vehicle_id, r)
                for value in results
                for r in value.records
                if period.start <= r.date <= period.end
            ],
            key=lambda pair: (pair[1].date, pair[1].day_sequence, pair[1].id),
            reverse=True,
        )[:5]
        return {
            "period": period_data(period),
            "available_vehicles": list(vehicles_for(request.user).values("id", "name", "status")),
            "assignment_rule": "end_refueling_date",
            "explanation": ASSIGNMENT,
            "purchases": {
                "amount": number(purchases.amount, 2),
                "liters": number(purchases.liters, 3),
                "count": purchases.count,
                "realized_unit_price": number(purchases.unit_price),
            },
            "consumption_l_100km": number(groups[0].totals.consumption) if len(groups) == 1 else None,
            "purchase_cost_czk_100km": number(groups[0].totals.cost_per_100km) if len(groups) == 1 else None,
            "consumption_by_fuel": [{"fuel_type": g.fuel_type, **totals_data(g.totals)} for g in groups],
            "comparison": comparison,
            "coverage": {
                "valid_intervals": len(valid),
                "excluded_intervals": len(candidates) - len(valid),
                "distance_km": totals.distance_km,
                "start_date": min((i.start.date for i in valid), default=None),
                "end_date": max((i.end.date for i in valid), default=None),
                "reasons": [{"code": code, "count": count} for code, count in sorted(reasons.items())],
                "vehicles": vehicle_info,
            },
            "charts": {
                "purchases": purchase_points,
                "consumption": [interval_data(i, period) for i in candidates],
            },
            "recent_refuelings": [
                {
                    "vehicle_id": vid,
                    "vehicle_name": vehicles[vid].name,
                    **record_data(row),
                }
                for vid, row in recent
            ],
        }


def intervals(request, params, vehicle_id, detail=False):
    with snapshot(request):
        period, _, _, results = load(request, params, vehicle_id)
        value = results[0]
        selected = [i for i in value.intervals if period.start <= i.end.date <= period.end]
        selected.sort(key=lambda i: (i.end.date, i.end.day_sequence), reverse=True)
        if detail:
            match = next(
                (
                    i
                    for i in selected
                    if i.start.id == str(params["start_id"]) and i.end.id == str(params["end_id"])
                ),
                None,
            )
            if match is None:
                raise Problem(
                    "not_found",
                    "Tento interval není v aktuální historii nebo období dostupný.",
                    404,
                )
            return {
                **interval_data(match, period),
                "records": [
                    dict(record_data(row), used_for_totals=index > 0)
                    for index, row in enumerate(match.records)
                ],
                "period": period_data(period),
                "history_revision": vehicles_for(request.user).get(pk=vehicle_id).history_revision,
            }
        return [interval_data(i, period) for i in selected]
