from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.core.serializers import StrictSerializer

from .models import VehicleEvent


class EventInput(StrictSerializer):
    kind = serializers.ChoiceField(choices=["SERVICE", "INSPECTION", "INSURANCE", "REMINDER", "ENERGY"])
    title = serializers.CharField(max_length=150)
    date = serializers.DateField()
    note = serializers.CharField(max_length=2000, allow_blank=True, required=False)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal(0), required=False)
    odometer_km = serializers.IntegerField(min_value=0, max_value=99999999, allow_null=True, required=False)
    due_date = serializers.DateField(allow_null=True, required=False)
    due_odometer_km = serializers.IntegerField(
        min_value=0, max_value=99999999, allow_null=True, required=False
    )
    notice_days = serializers.IntegerField(min_value=0, max_value=365, required=False)
    notice_km = serializers.IntegerField(min_value=0, max_value=100000, required=False)
    closed = serializers.BooleanField(required=False)
    quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        min_value=Decimal(".001"),
        allow_null=True,
        required=False,
    )
    unit = serializers.ChoiceField(choices=["", "kg", "kWh"], required=False)

    def validate(self, data):
        if data["kind"] != "REMINDER" and data["date"] > timezone.localdate():
            raise serializers.ValidationError({"date": "Skutečná událost nesmí být v budoucnosti."})
        if data["kind"] == "ENERGY":
            if data.get("quantity") is None or data.get("unit") not in ["kg", "kWh"]:
                raise serializers.ValidationError("Nákup energie vyžaduje množství a kg/kWh.")
        elif data.get("quantity") is not None or data.get("unit"):
            raise serializers.ValidationError("Množství a jednotka patří pouze nákupu energie.")
        if data["kind"] in ["INSPECTION", "INSURANCE"] and not data.get("due_date"):
            raise serializers.ValidationError({"due_date": "Uveďte platnost do."})
        if data["kind"] == "REMINDER" and not (
            data.get("due_date") or data.get("due_odometer_km") is not None
        ):
            raise serializers.ValidationError("Připomínka vyžaduje termín nebo km.")
        if data.get("due_date") and data["due_date"] < data["date"]:
            raise serializers.ValidationError({"due_date": "Termín nesmí předcházet datu události."})
        return data


class EventOutput(serializers.ModelSerializer):
    etag = serializers.SerializerMethodField()

    def get_etag(self, obj) -> str:
        return f'"event:{obj.pk}:{obj.version}"'

    class Meta:
        model = VehicleEvent
        fields = [
            "id",
            "vehicle_id",
            "author_id",
            *EventInput().fields,
            "version",
            "created_at",
            "etag",
        ]
        read_only_fields = fields


class ImportInput(StrictSerializer):
    csv_text = serializers.CharField(max_length=128 * 1024, trim_whitespace=False)
    kind = serializers.ChoiceField(choices=["FUEL", "EVENT"], default="FUEL")


class ConfirmInput(StrictSerializer):
    confirmed = serializers.BooleanField()
    confirmed_warning_codes = serializers.ListField(
        child=serializers.CharField(max_length=50), max_length=30, default=list
    )

    def validate_confirmed(self, value):
        if not value:
            raise serializers.ValidationError("Potvrďte zobrazený návrh.")
        return value
