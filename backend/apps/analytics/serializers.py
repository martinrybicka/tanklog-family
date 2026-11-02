from rest_framework import serializers

from apps.core.serializers import StrictSerializer


class StatisticsFilters(StrictSerializer):
    period = serializers.ChoiceField(choices=["day", "week", "month", "year", "custom"], required=False)
    anchor_date = serializers.DateField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    vehicle_id = serializers.UUIDField(required=False)
    group_by = serializers.ChoiceField(choices=["day", "week", "month"], required=False)

    def validate(self, data):
        if data.get("period", "month") == "custom":
            if "anchor_date" in data or not {"date_from", "date_to"} <= data.keys():
                raise serializers.ValidationError("Vlastní období vyžaduje od–do a nepřijímá anchor_date.")
            if data["date_from"] > data["date_to"]:
                raise serializers.ValidationError("Datum od musí být nejvýše datum do.")
        elif "date_from" in data or "date_to" in data:
            raise serializers.ValidationError("Datumy od–do patří pouze k vlastnímu období.")
        return data


class IntervalFilters(StatisticsFilters):
    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False)


class IntervalDetailFilters(StatisticsFilters):
    start_id = serializers.UUIDField()
    end_id = serializers.UUIDField()


# Výstupní kontrakty pro OpenAPI. Hodnoty služba sestaví uvnitř read-only snapshotu.
class PeriodOutput(serializers.Serializer):
    period = serializers.CharField()
    anchor_date = serializers.DateField(allow_null=True)
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    timezone = serializers.CharField()
    group_by = serializers.CharField()


class TotalsOutput(serializers.Serializer):
    liters = serializers.CharField()
    amount = serializers.CharField()
    distance_km = serializers.IntegerField()
    valid_intervals = serializers.IntegerField()
    excluded_intervals = serializers.IntegerField()
    consumption_l_100km = serializers.CharField(allow_null=True)
    purchase_cost_czk_100km = serializers.CharField(allow_null=True)


class IntervalOutput(serializers.Serializer):
    vehicle_id = serializers.UUIDField()
    start_id = serializers.UUIDField()
    end_id = serializers.UUIDField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    start_odometer_km = serializers.IntegerField()
    end_odometer_km = serializers.IntegerField()
    liters = serializers.CharField()
    amount = serializers.CharField()
    distance_km = serializers.IntegerField()
    fuel_type = serializers.CharField()
    status = serializers.CharField()
    reasons = serializers.ListField(child=serializers.CharField())
    warnings = serializers.ListField(child=serializers.CharField())
    consumption_l_100km = serializers.CharField(allow_null=True)
    purchase_cost_czk_100km = serializers.CharField(allow_null=True)
    crosses_period_start = serializers.BooleanField()
    assignment_rule = serializers.CharField()
    explanation = serializers.CharField()
    record_ids = serializers.ListField(child=serializers.UUIDField())


class RecordOutput(serializers.Serializer):
    id = serializers.UUIDField()
    date = serializers.DateField()
    day_sequence = serializers.IntegerField()
    liters = serializers.CharField()
    total_amount = serializers.CharField()
    fuel_type = serializers.CharField()
    odometer_km = serializers.IntegerField(allow_null=True)
    is_full_tank = serializers.BooleanField()
    break_before = serializers.BooleanField()


class EvidenceOutput(RecordOutput):
    used_for_totals = serializers.BooleanField()


class IntervalDetailOutput(IntervalOutput):
    records = EvidenceOutput(many=True)
    period = PeriodOutput()
    history_revision = serializers.IntegerField()


class IntervalPageOutput(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = IntervalOutput(many=True)


class PurchaseOutput(serializers.Serializer):
    amount = serializers.CharField()
    liters = serializers.CharField()
    count = serializers.IntegerField()
    realized_unit_price = serializers.CharField(allow_null=True)


class PurchasePointOutput(serializers.Serializer):
    date = serializers.DateField()
    amount = serializers.CharField()
    liters = serializers.CharField()
    count = serializers.IntegerField()
    unit_price = serializers.CharField(allow_null=True)


class FuelOutput(TotalsOutput):
    fuel_type = serializers.CharField()


class VehicleCoverageOutput(TotalsOutput):
    vehicle_id = serializers.UUIDField()
    name = serializers.CharField()
    status = serializers.CharField()
    reasons = serializers.ListField(child=serializers.CharField())
    history_revision = serializers.IntegerField()
    missing_odometer_ids = serializers.ListField(child=serializers.UUIDField())
    open_record_ids = serializers.ListField(child=serializers.UUIDField())


class ReasonCountOutput(serializers.Serializer):
    code = serializers.CharField()
    count = serializers.IntegerField()


class CoverageOutput(serializers.Serializer):
    valid_intervals = serializers.IntegerField()
    excluded_intervals = serializers.IntegerField()
    distance_km = serializers.IntegerField()
    start_date = serializers.DateField(allow_null=True)
    end_date = serializers.DateField(allow_null=True)
    reasons = ReasonCountOutput(many=True)
    vehicles = VehicleCoverageOutput(many=True)


class ComparisonOutput(serializers.Serializer):
    standard = serializers.CharField()
    difference_l_100km = serializers.CharField()
    difference_percent = serializers.CharField()
    methodology = serializers.CharField()
    source = serializers.CharField(allow_blank=True)
    source_note = serializers.CharField(allow_blank=True)


class AvailableVehicleOutput(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    status = serializers.CharField()


class RecentRefuelingOutput(RecordOutput):
    vehicle_id = serializers.UUIDField()
    vehicle_name = serializers.CharField()


class ChartsOutput(serializers.Serializer):
    purchases = PurchasePointOutput(many=True)
    consumption = IntervalOutput(many=True)


class DashboardOutput(serializers.Serializer):
    period = PeriodOutput()
    available_vehicles = AvailableVehicleOutput(many=True)
    assignment_rule = serializers.CharField()
    explanation = serializers.CharField()
    purchases = PurchaseOutput()
    consumption_l_100km = serializers.CharField(allow_null=True)
    purchase_cost_czk_100km = serializers.CharField(allow_null=True)
    consumption_by_fuel = FuelOutput(many=True)
    comparison = ComparisonOutput(allow_null=True)
    coverage = CoverageOutput()
    charts = ChartsOutput()
    recent_refuelings = RecentRefuelingOutput(many=True)
