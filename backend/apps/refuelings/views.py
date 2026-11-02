from django.http import HttpResponse
from django.utils import timezone
from django.utils.http import content_disposition_header
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.views import validated
from apps.core.errors import Problem
from apps.core.pagination import Pagination
from apps.vehicles.selectors import vehicle_for, vehicles_for

from . import receipts, services
from .export import export_xlsx
from .models import ReceiptAttachment, Refueling
from .presentation import present
from .selectors import filtered, payer_options, refueling_for, rights
from .serializers import Filters, OrderDate, OrderInput, RefuelingInput, RefuelingUpdate


def item_response(request, item, status=200):
    vehicle = vehicle_for(request.user, item.vehicle_id)
    response = Response(present(request, item, vehicle), status=status)
    response["ETag"] = services.etag(item)
    return response


class RefuelingsView(APIView):
    @extend_schema(operation_id="refuelings_list", parameters=[Filters], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        params = validated(Filters, request.query_params.dict())
        paginator = Pagination()
        items = paginator.paginate_queryset(filtered(request.user, params), request)
        vehicles = {v.pk: v for v in vehicles_for(request.user).filter(pk__in={r.vehicle_id for r in items})}
        return paginator.get_paginated_response(
            [present(request, r, vehicles[r.vehicle_id]) for r in items if r.vehicle_id in vehicles]
        )

    @extend_schema(request=RefuelingInput, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        item, replayed = services.create(request, validated(RefuelingInput, request.data))
        response = item_response(request, item, 200 if replayed else 201)
        if replayed:
            response["Idempotency-Replayed"] = "true"
        return response


class RefuelingDetailView(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, item_id):
        return item_response(request, refueling_for(request.user, item_id))

    @extend_schema(request=RefuelingUpdate, responses=OpenApiTypes.OBJECT)
    def patch(self, request, item_id):
        serializer = RefuelingUpdate(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return item_response(request, services.update(request, item_id, serializer.validated_data))

    @extend_schema(responses={204: None})
    def delete(self, request, item_id):
        services.delete(request, item_id)
        return Response(status=204)


class ExportView(APIView):
    @extend_schema(
        parameters=[Filters],
        responses={
            (200, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"): OpenApiTypes.BINARY
        },
    )
    def get(self, request):
        content = export_xlsx(request.user, validated(Filters, request.query_params.dict()))
        response = HttpResponse(
            content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="tankovani.xlsx"'
        return response


class ReceiptView(APIView):
    parser_classes = [MultiPartParser]

    @extend_schema(responses=OpenApiTypes.BINARY)
    def get(self, request, item_id):
        item = refueling_for(request.user, item_id)
        variant = request.query_params.get("variant", "original")
        if variant not in ["preview", "original"]:
            raise ValidationError({"variant": "Zvolte original nebo preview."})
        attachment = ReceiptAttachment.objects.filter(refueling=item).first()
        if not attachment:
            raise Problem("not_found", "Účtenka není dostupná.", 404)
        preview = variant == "preview"
        response = HttpResponse(
            bytes(attachment.preview_bytes if preview else attachment.original_bytes),
            content_type="image/jpeg" if preview else attachment.content_type,
        )
        response["Content-Disposition"] = content_disposition_header(
            not preview, "nahled.jpg" if preview else attachment.original_filename
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response

    def upload(self, request, item_id, replace):
        # Práva a ETag ověřit ještě před drahým dekódováním; v transakci znovu.
        item = refueling_for(request.user, item_id)
        vehicle = vehicle_for(request.user, item.vehicle_id)
        services.authorize(request.user, vehicle, "edit", item)
        services.require_tag(request, services.etag(item))
        if int(request.META.get("CONTENT_LENGTH") or 0) > 12 * 1024 * 1024:
            raise Problem("file_too_large", "Požadavek přesahuje 12 MiB.", 413)
        receipts.check_rate(request, item)
        if set(request.data) != {"file"} or len(request.FILES.getlist("file")) != 1:
            raise ValidationError({"file": "Nahrajte právě jeden soubor file."})
        payload = receipts.validate_image(request.FILES["file"])
        return item_response(
            request, receipts.save(request, item_id, payload, replace), 200 if replace else 201
        )

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
                "required": ["file"],
            }
        },
        responses=OpenApiTypes.OBJECT,
    )
    def post(self, request, item_id):
        return self.upload(request, item_id, False)

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
                "required": ["file"],
            }
        },
        responses=OpenApiTypes.OBJECT,
    )
    def put(self, request, item_id):
        return self.upload(request, item_id, True)

    @extend_schema(responses={204: None})
    def delete(self, request, item_id):
        receipts.delete(request, item_id)
        return Response(status=204)


class OrderView(APIView):
    @extend_schema(parameters=[OrderDate], responses=OpenApiTypes.OBJECT)
    def get(self, request, vehicle_id):
        params = validated(OrderDate, request.query_params.dict())
        vehicle = vehicle_for(request.user, vehicle_id)
        response = Response(
            {
                "date": params["date"],
                "ordered_ids": list(
                    Refueling.objects.filter(vehicle=vehicle, date=params["date"])
                    .order_by("day_sequence")
                    .values_list("id", flat=True)
                ),
            }
        )
        response["ETag"] = services.history_etag(vehicle)
        return response

    @extend_schema(request=OrderInput, responses=OpenApiTypes.OBJECT)
    def put(self, request, vehicle_id):
        vehicle = services.reorder(request, vehicle_id, validated(OrderInput, request.data))
        response = Response({"history_revision": vehicle.history_revision})
        response["ETag"] = services.history_etag(vehicle)
        return response


class PayerOptionsView(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, vehicle_id):
        vehicle = vehicle_for(request.user, vehicle_id)
        if not any(rights(request.user, vehicle).values()):
            raise Problem("permission_denied", "Volby plátce nejsou dostupné.", 403)
        return Response(
            {
                "results": [
                    {"id": u.pk, "display_name": u.display_name or u.username} for u in payer_options(vehicle)
                ],
                "today": timezone.localdate(),
            }
        )
