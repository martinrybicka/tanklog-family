from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import serializers
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import Administrator
from apps.accounts.views import validated
from apps.core.errors import Problem
from apps.core.serializers import StrictSerializer
from apps.extensions.integrations import reserve
from apps.refuelings import receipts
from apps.refuelings import services as fuel
from apps.refuelings.serializers import RefuelingInput
from apps.refuelings.views import item_response
from apps.vehicles.selectors import vehicle_for, vehicles_for

from . import services
from .models import ReceiptDraft


class PreferenceInput(StrictSerializer):
    default_vehicle_id = serializers.UUIDField(allow_null=True)


class UploadInput(StrictSerializer):
    vehicle_id = serializers.UUIDField()
    file = serializers.FileField()


def preference_response(user):
    data, tag = services.preference(user)
    response = Response(data)
    response["ETag"] = tag
    return response


class PreferenceView(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return preference_response(request.user)


class AdminPreferenceView(APIView):
    permission_classes = [Administrator]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, user_id):
        return preference_response(get_object_or_404(User, pk=user_id))

    @extend_schema(request=PreferenceInput, responses=OpenApiTypes.OBJECT)
    def put(self, request, user_id):
        data = validated(PreferenceInput, request.data)
        services.configure(request, user_id, data["default_vehicle_id"])
        return preference_response(get_object_or_404(User, pk=user_id))


def output(draft):
    return {
        "id": str(draft.pk),
        "vehicle_id": str(draft.vehicle_id),
        "suggestions": draft.suggestions,
        "result_id": str(draft.result_id) if draft.result_id else None,
        "created_at": draft.created_at,
        "preview_url": f"/api/v1/family/receipts/{draft.pk}/image/",
    }


def draft_response(draft, status=200):
    response = Response(output(draft), status=status)
    response["ETag"] = services.draft_tag(draft)
    return response


class DraftsView(APIView):
    parser_classes = [MultiPartParser]

    @extend_schema(operation_id="family_receipts_list", responses=OpenApiTypes.OBJECT)
    def get(self, request):
        drafts = (
            ReceiptDraft.objects.filter(
                user=request.user, result_id__isnull=True, vehicle__in=vehicles_for(request.user)
            )
            .defer("original", "preview")
            .order_by("-created_at", "-id")[:20]
        )
        return Response({"results": [output(draft) for draft in drafts]})

    @extend_schema(request=UploadInput, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        if int(request.META.get("CONTENT_LENGTH") or 0) > 12 * 1024**2:
            raise Problem("file_too_large", "Účtenka smí mít nejvýše 10 MiB.", 413)
        data = validated(UploadInput, request.data)
        car = vehicle_for(request.user, data["vehicle_id"])
        fuel.authorize(request.user, car, "create")
        reserve(request, "family-upload", 20, 40)
        payload = receipts.validate_image(data["file"])
        return draft_response(services.upload(request, car.pk, payload), 201)


class DraftView(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, draft_id):
        return draft_response(services.draft_for(request, draft_id))

    @extend_schema(responses={204: None})
    def delete(self, request, draft_id):
        from django.db import transaction

        from apps.vehicles.services import lock_users, lock_vehicle

        with transaction.atomic():
            lock_users(request)
            draft = services.draft_for(request, draft_id)
            lock_vehicle(request, draft.vehicle_id, manage=False)
            fuel.require_tag(request, services.draft_tag(draft))
            if draft.result_id:
                raise Problem("draft_completed", "Uložené tankování spravujte v historii.", 409)
            draft.delete()
        return Response(status=204)


class RecognizeView(APIView):
    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request, draft_id):
        if request.data:
            raise serializers.ValidationError("Rozpoznání nepřijímá další údaje.")
        return draft_response(services.recognize(request, draft_id))


class CompleteView(APIView):
    @extend_schema(request=RefuelingInput, responses=OpenApiTypes.OBJECT)
    def post(self, request, draft_id):
        return item_response(
            request, services.complete(request, draft_id, validated(RefuelingInput, request.data)), 201
        )


class ImageView(APIView):
    @extend_schema(responses={(200, "image/jpeg"): OpenApiTypes.BINARY})
    def get(self, request, draft_id):
        draft = services.draft_for(request, draft_id)
        response = HttpResponse(bytes(draft.preview), content_type="image/jpeg")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
