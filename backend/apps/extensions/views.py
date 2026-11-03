from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.views import validated
from apps.audit.models import record
from apps.core.pagination import Pagination
from apps.core.serializers import StrictSerializer
from apps.vehicles.selectors import vehicle_for
from apps.vehicles.serializers import VehicleInput
from apps.vehicles.services import bump, lock_users, lock_vehicle, require_version

from . import integrations, ocr, services
from .models import ImportBatch, VehicleImage
from .serializers import ConfirmInput, EventInput, EventOutput, ImportInput


def page(request, values):
    paginator = Pagination()
    return paginator.get_paginated_response(paginator.paginate_queryset(values, request))


def event_response(item, status=200):
    response = Response(EventOutput(item).data, status=status)
    response["ETag"] = services.tag(item)
    return response


class EventsView(APIView):
    @extend_schema(responses=EventOutput(many=True))
    def get(self, request, vehicle_id):
        vehicle_for(request.user, vehicle_id)
        items = services.events_for(request.user).filter(vehicle_id=vehicle_id)
        paginator = Pagination()
        selected = paginator.paginate_queryset(items, request)
        return paginator.get_paginated_response(
            [dict(EventOutput(item).data, etag=services.tag(item)) for item in selected]
        )

    @extend_schema(request=EventInput, responses=EventOutput)
    def post(self, request, vehicle_id):
        return event_response(
            services.save_event(request, vehicle_id, validated(EventInput, request.data)),
            201,
        )


class EventDetailView(APIView):
    @extend_schema(responses=EventOutput)
    def get(self, request, vehicle_id, event_id):
        return event_response(
            get_object_or_404(services.events_for(request.user), pk=event_id, vehicle_id=vehicle_id)
        )

    @extend_schema(request=EventInput, responses=EventOutput)
    def put(self, request, vehicle_id, event_id):
        return event_response(
            services.save_event(request, vehicle_id, validated(EventInput, request.data), event_id)
        )

    @extend_schema(responses={204: None})
    def delete(self, request, vehicle_id, event_id):
        services.save_event(request, vehicle_id, {}, event_id, delete=True)
        return Response(status=204)


class ReminderView(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return page(request, services.reminders(request.user))


class EnergyTotalsView(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, vehicle_id):
        return Response(services.totals(request.user, vehicle_id))


def batch_output(batch):
    return {
        "id": str(batch.pk),
        "kind": batch.kind,
        "rows": batch.rows,
        "errors": batch.errors,
        "warnings": batch.warnings,
        "completed": batch.completed,
        "results": batch.results,
        "created_at": batch.created_at,
        "csv_text": batch.raw,
    }


class ImportView(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, vehicle_id):
        vehicle_for(request.user, vehicle_id)
        batches = ImportBatch.objects.filter(vehicle_id=vehicle_id, user=request.user).order_by(
            "-created_at", "-id"
        )
        paginator = Pagination()
        selected = paginator.paginate_queryset(batches, request)
        return paginator.get_paginated_response(
            [
                {
                    "id": str(item.pk),
                    "created_at": item.created_at,
                    "kind": item.kind,
                    "completed": item.completed,
                }
                for item in selected
            ]
        )

    @extend_schema(request=ImportInput, responses=OpenApiTypes.OBJECT)
    def post(self, request, vehicle_id):
        return Response(
            batch_output(services.preview_import(request, vehicle_id, validated(ImportInput, request.data))),
            status=201,
        )


class ImportDetailView(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, batch_id):
        batch = get_object_or_404(ImportBatch, pk=batch_id, user=request.user)
        vehicle_for(request.user, batch.vehicle_id)
        return Response(batch_output(batch))

    @extend_schema(request=ConfirmInput, responses=OpenApiTypes.OBJECT)
    def post(self, request, batch_id):
        values = validated(ConfirmInput, request.data)
        return Response(
            batch_output(services.confirm_import(request, batch_id, values["confirmed_warning_codes"]))
        )


class LookupInput(StrictSerializer):
    vin = serializers.CharField(max_length=17)
    vehicle_id = serializers.UUIDField(required=False)

    def validate_vin(self, value):
        return VehicleInput().validate_vin(value) or ""


def lookup_output(result):
    return {
        "id": str(result.pk),
        "vin": result.vin,
        "suggestions": result.suggestions,
        "applied_fields": result.applied_fields,
        "created_at": result.created_at,
        "expired": result.created_at < timezone.now() - timedelta(hours=24),
        "source": "Registr silničních vozidel",
        "notes": {
            "consumption": str(result.raw["Data"].get("SpotrebaNa100Km") or ""),
            "methodology": str(result.raw["Data"].get("SpotrebaMetodika") or ""),
            "power": str(result.raw["Data"].get("MotorMaxVykon") or ""),
        },
    }


class LookupView(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        from apps.vehicles.selectors import vehicles_for

        from .models import VehicleDataSnapshot

        snapshots = VehicleDataSnapshot.objects.filter(applicant=request.user).filter(
            Q(vehicle__isnull=True) | Q(vehicle__in=vehicles_for(request.user))
        )
        vehicle_id = (
            serializers.UUIDField().run_validation(request.query_params["vehicle_id"])
            if "vehicle_id" in request.query_params
            else None
        )
        if vehicle_id:
            integrations.manageable(request, vehicle_id)
            snapshots = snapshots.filter(vehicle_id=vehicle_id)
        else:
            snapshots = snapshots.filter(vehicle__isnull=True)
        return page(
            request,
            [lookup_output(item) for item in snapshots.order_by("-created_at")[:25]],
        )

    @extend_schema(request=LookupInput, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        values = validated(LookupInput, request.data)
        result = integrations.lookup(request, values["vin"], values.get("vehicle_id"))
        return Response(lookup_output(result), status=201)


def image_output(item):
    return {
        "id": str(item.pk),
        "metadata": {key: value for key, value in item.metadata.items() if key != "url"},
        "url": f"/api/v1/vehicle-images/{item.pk}/",
        "match": {key: value for key, value in item.match.items() if key != "vin_hash"},
    }


class PhotoSearchView(APIView):
    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request, vehicle_id):
        validated(StrictSerializer, request.data)
        return Response(
            {"results": [image_output(item) for item in integrations.search_photos(request, vehicle_id)]}
        )


class PhotoInput(StrictSerializer):
    image_id = serializers.UUIDField()
    confirmed = serializers.BooleanField()

    def validate_confirmed(self, value):
        if not value:
            raise serializers.ValidationError("Potvrďte shodu modelu a licenční údaje.")
        return value


class PhotoSelectView(APIView):
    @extend_schema(request=PhotoInput, responses={204: None})
    def post(self, request, vehicle_id):
        values = validated(PhotoInput, request.data)
        integrations.choose_photo(request, vehicle_id, values["image_id"])
        return Response(status=204)

    @extend_schema(responses={204: None})
    def delete(self, request, vehicle_id):
        with transaction.atomic():
            lock_users(request)
            car = lock_vehicle(request, vehicle_id)
            require_version(request, car)
            VehicleImage.objects.filter(vehicle=car).delete()
            record(request, "vehicle.photo_removed", car, vehicle_id=car.pk)
            bump(car)
        return Response(status=204)


class PhotoContentView(APIView):
    @extend_schema(responses=OpenApiTypes.BINARY)
    def get(self, request, image_id):
        item = integrations.photo_for(request, image_id)
        response = HttpResponse(bytes(item.preview), content_type="image/jpeg")
        response["Content-Disposition"] = 'inline; filename="ilustracni-fotografie.jpg"'
        return response


class OcrView(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, item_id):
        from apps.refuelings.selectors import refueling_for

        from .models import ReceiptExtraction

        item = refueling_for(request.user, item_id)
        result = ReceiptExtraction.objects.filter(refueling=item).order_by("-created_at", "-id").first()
        if result is None:
            from apps.core.errors import Problem

            raise Problem("not_found", "Uložený výsledek OCR není dostupný.", 404)
        return Response(ocr.extraction(request, item_id, result.pk))

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request, item_id):
        validated(StrictSerializer, request.data)
        item = ocr.recognize(request, item_id)
        return Response(ocr.extraction(request, item_id, item.pk), status=201)


class ExtractionView(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, item_id, extraction_id):
        return Response(ocr.extraction(request, item_id, extraction_id))
