"""Nastavení RSV: šifrovaný klíč v DB, nikdy ve čtecí odpovědi nebo auditu."""

import base64
import hashlib
from urllib.parse import urlencode

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import connection, transaction
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import Administrator
from apps.accounts.views import validated
from apps.audit.models import record
from apps.core.errors import Problem
from apps.core.serializers import StrictSerializer
from apps.refuelings.services import require_tag
from apps.vehicles.serializers import VehicleInput
from apps.vehicles.services import lock_users

from .models import IntegrationSetting


def cipher():
    return Fernet(
        base64.urlsafe_b64encode(hashlib.sha256((settings.SECRET_KEY + ":tanklog:rsv:v1").encode()).digest())
    )


def current_key():
    row = IntegrationSetting.objects.filter(name="rsv").first()
    if row:
        try:
            return cipher().decrypt(row.encrypted_secret.encode()).decode()
        except InvalidToken as error:
            raise Problem(
                "integration_key_unreadable", "Klíč nelze dešifrovat. Správce jej musí uložit znovu.", 503
            ) from error
    return settings.RSV_API_KEY


def configuration():
    row = IntegrationSetting.objects.filter(name="rsv").first()
    return {
        "configured": bool(row or settings.RSV_API_KEY),
        "source": "database" if row else ("environment" if settings.RSV_API_KEY else "none"),
        "updated_at": row.updated_at if row else None,
    }, f'"rsv-setting:{row.version if row else 0}"'


class KeyInput(StrictSerializer):
    api_key = serializers.CharField(max_length=256, min_length=8, trim_whitespace=True, write_only=True)

    def validate_api_key(self, value):
        if any(c.isspace() or ord(c) < 33 or ord(c) > 126 for c in value):
            raise serializers.ValidationError("Klíč nesmí obsahovat mezery nebo řídicí znaky.")
        return value


class ProbeInput(StrictSerializer):
    vin = serializers.CharField(max_length=17, required=False, allow_blank=True)

    def validate_vin(self, value):
        return VehicleInput().validate_vin(value) if value else ""


@transaction.atomic
def save_key(request, key):
    lock_users(request, admin=True)
    # Společný zámek brání souběžnému přepsání klíče dvěma správci i při prvním uložení.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(83641527)")
    _, tag = configuration()
    require_tag(request, tag)
    row = IntegrationSetting.objects.filter(name="rsv").first()
    row = row or IntegrationSetting(name="rsv", version=0)
    row.encrypted_secret = cipher().encrypt(key.encode()).decode()
    row.version += 1
    row.save()
    record(request, "integration.rsv_key_updated", changes={"version": row.version})


def test_connection(request, vin):
    from .integrations import reserve
    from .providers import fetch_json

    with transaction.atomic():
        lock_users(request, admin=True)
    reserve(request, "rsv")
    key = current_key()
    if not key:
        raise Problem("provider_not_configured", "Nejprve uložte API klíč.", 503)
    payload = fetch_json(
        "https://api.dataovozidlech.cz/api/vehicletechnicaldata/v2?"
        + urlencode({"vin": vin or "TMBEFF654V7529422"}),
        {"API_KEY": key},
    )
    if not isinstance(payload, dict) or payload.get("Status") not in (1, 3):
        raise Problem(
            "provider_invalid", "Registr vrátil neočekávanou odpověď; spojení nebylo potvrzeno.", 502
        )
    with transaction.atomic():
        lock_users(request, admin=True)
        if current_key() != key:
            raise Problem("stale_version", "Klíč byl mezitím změněn. Spusťte test znovu.", 412)
        record(request, "integration.rsv_tested", changes={"vehicle_found": bool(payload.get("Data"))})
    found = payload.get("Status") == 1 and bool(payload.get("Data"))
    return {
        "connected": True,
        "vehicle_found": found,
        "message": "Spojení funguje a registr přijal API klíč."
        + (" Vozidlo bylo nalezeno." if found else " Testovací VIN nebyl nalezen; nejde o chybu spojení."),
    }


class RsvSettingsView(APIView):
    permission_classes = [Administrator]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        data, tag = configuration()
        response = Response(data)
        response["ETag"] = tag
        return response

    @extend_schema(request=KeyInput, responses=OpenApiTypes.OBJECT)
    def put(self, request):
        save_key(request, validated(KeyInput, request.data)["api_key"])
        return self.get(request)


class RsvTestView(APIView):
    permission_classes = [Administrator]

    @extend_schema(request=ProbeInput, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        return Response(test_connection(request, validated(ProbeInput, request.data).get("vin", "")))
