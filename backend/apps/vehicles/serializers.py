import re
from decimal import Decimal

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.serializers import StrictSerializer

from .models import Vehicle, VehicleAccess
from .selectors import effective_role, permissions


class VehicleInput(StrictSerializer):
    lookup_id = serializers.UUIDField(required=False, write_only=True)
    lookup_fields = serializers.ListField(
        child=serializers.ChoiceField(
            choices=["make", "model", "fuel_type", "engine_displacement_cc", "power_kw"]
        ),
        max_length=5,
        required=False,
        write_only=True,
    )

    def validate(self, data):
        if bool(data.get("lookup_id")) != bool(data.get("lookup_fields")):
            raise serializers.ValidationError({"lookup_fields": "Návrh VIN vyžaduje výslovný výběr polí."})
        return data

    name = serializers.CharField(max_length=100)
    make = serializers.CharField(max_length=100)
    model = serializers.CharField(max_length=100)
    fuel_type = serializers.ChoiceField(choices=Vehicle.Fuel.choices)
    initial_odometer_km = serializers.IntegerField(min_value=0, max_value=99999999)
    manufacture_year = serializers.IntegerField(min_value=1886, allow_null=True, required=False)
    registration_plate = serializers.CharField(max_length=20, allow_blank=True, required=False)
    vin = serializers.CharField(max_length=17, allow_blank=True, allow_null=True, required=False)
    consumption_mode = serializers.ChoiceField(choices=Vehicle.ConsumptionMode.choices, required=False)
    engine_displacement_cc = serializers.IntegerField(
        min_value=1, max_value=2147483647, allow_null=True, required=False
    )
    power_kw = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=Decimal("0.01"),
        allow_null=True,
        required=False,
    )
    tank_capacity_l = serializers.DecimalField(
        max_digits=8,
        decimal_places=3,
        min_value=Decimal("0.001"),
        allow_null=True,
        required=False,
    )
    standard_consumption_l_100km = serializers.DecimalField(
        max_digits=7,
        decimal_places=3,
        min_value=Decimal("0.001"),
        allow_null=True,
        required=False,
    )
    standard_methodology = serializers.ChoiceField(choices=Vehicle.Methodology.choices, required=False)
    standard_source = serializers.CharField(max_length=500, allow_blank=True, required=False)
    standard_source_note = serializers.CharField(max_length=2000, allow_blank=True, required=False)

    def validate_manufacture_year(self, value):
        if value is not None and value > timezone.localdate().year + 1:
            raise serializers.ValidationError("Rok smí být nejvýše aktuální rok + 1.")
        return value

    def validate_vin(self, value):
        value = (value or "").strip().upper()
        if value and not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", value):
            raise serializers.ValidationError("VIN musí mít 17 znaků bez písmen I, O a Q.")
        return value or None

    def validate_registration_plate(self, value):
        return " ".join(value.upper().split())


class VehicleSerializer(serializers.ModelSerializer):
    photo = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_photo(self, obj):
        from apps.extensions.integrations import photo_match
        from apps.extensions.models import VehicleImage
        from apps.extensions.views import image_output

        item = VehicleImage.objects.filter(vehicle=obj, status="ACTIVE").defer("original", "preview").first()
        return image_output(item) if item and item.match == photo_match(obj) else None

    effective_role = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField())
    def get_effective_role(self, obj):
        return effective_role(self.context["request"].user, obj)

    @extend_schema_field(serializers.DictField(child=serializers.BooleanField()))
    def get_permissions(self, obj):
        return permissions(self.context["request"].user, obj)

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "owner_id",
            *[key for key in VehicleInput().fields if key not in ["lookup_id", "lookup_fields"]],
            "photo",
            "status",
            "version",
            "history_revision",
            "created_at",
            "updated_at",
            "archived_at",
            "effective_role",
            "permissions",
        ]
        read_only_fields = fields


class AccessInput(StrictSerializer):
    user_id = serializers.UUIDField()
    role = serializers.ChoiceField(choices=VehicleAccess.Role.choices)


class AccessUpdate(StrictSerializer):
    role = serializers.ChoiceField(choices=VehicleAccess.Role.choices)


class TransferInput(StrictSerializer):
    new_owner_id = serializers.UUIDField()
    previous_owner_role = serializers.ChoiceField(choices=VehicleAccess.Role.choices, required=False)
    current_password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)


class AccessSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    display_name = serializers.CharField(source="user.display_name", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)

    class Meta:
        model = VehicleAccess
        fields = [
            "id",
            "vehicle_id",
            "user_id",
            "username",
            "display_name",
            "is_active",
            "role",
            "granted_by_id",
            "version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class VehicleFilters(StrictSerializer):
    status = serializers.ChoiceField(choices=["active", "archived", "all"], required=False)
    page = serializers.IntegerField(min_value=1, required=False)
