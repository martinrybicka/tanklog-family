from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.core.serializers import StrictSerializer
from apps.vehicles.models import Vehicle

from .models import Refueling


class RefuelingInput(StrictSerializer):
    vehicle_id = serializers.UUIDField()
    date = serializers.DateField(required=False)
    day_sequence = serializers.IntegerField(min_value=1, required=False)
    liters = serializers.DecimalField(max_digits=10, decimal_places=3, min_value=Decimal(".001"))
    unit_price_entered = serializers.DecimalField(
        max_digits=10,
        decimal_places=4,
        min_value=Decimal("0"),
        allow_null=True,
        required=False,
    )
    total_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0"), required=False
    )
    odometer_km = serializers.IntegerField(min_value=0, max_value=99999999, allow_null=True, required=False)
    is_full_tank = serializers.BooleanField(required=False)
    break_before = serializers.BooleanField(required=False)
    fuel_type = serializers.ChoiceField(
        choices=[(value, label) for value, label in Vehicle.Fuel.choices if value not in ["CNG", "ELECTRIC"]],
        required=False,
    )
    station_code = serializers.ChoiceField(
        choices=Refueling.Station.choices, allow_blank=True, required=False
    )
    station_custom_name = serializers.CharField(max_length=120, allow_blank=True, required=False)
    note = serializers.CharField(max_length=2000, allow_blank=True, trim_whitespace=False, required=False)
    paid_by_user_id = serializers.UUIDField(allow_null=True, required=False)
    paid_by_label = serializers.CharField(max_length=150, allow_blank=True, required=False)
    confirmed_warning_codes = serializers.ListField(
        child=serializers.CharField(max_length=50), max_length=20, required=False
    )

    def validate_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("Datum tankování nesmí být v budoucnosti.")
        return value


class RefuelingUpdate(RefuelingInput):
    extraction_id = serializers.UUIDField(required=False)
    vehicle_id = None


class Filters(StrictSerializer):
    vehicle_id = serializers.UUIDField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    fuel_type = serializers.ChoiceField(
        choices=[(value, label) for value, label in Vehicle.Fuel.choices if value not in ["CNG", "ELECTRIC"]],
        required=False,
    )
    station_code = serializers.ChoiceField(
        choices=Refueling.Station.choices, allow_blank=True, required=False
    )
    search = serializers.CharField(max_length=200, required=False, allow_blank=True)
    ordering = serializers.ChoiceField(
        choices=[
            sign + field for field in ["date", "total_amount", "liters", "odometer_km"] for sign in ["", "-"]
        ],
        required=False,
    )
    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False)

    def validate(self, data):
        if data.get("date_from") and data.get("date_to") and data["date_from"] > data["date_to"]:
            raise serializers.ValidationError("Počáteční datum musí být nejvýše koncové datum.")
        return data


class OrderInput(StrictSerializer):
    date = serializers.DateField()
    ordered_ids = serializers.ListField(child=serializers.UUIDField(), max_length=1000)


class OrderDate(StrictSerializer):
    date = serializers.DateField()
