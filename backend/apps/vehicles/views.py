from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import Administrator
from apps.accounts.views import validated
from apps.core.pagination import Pagination

from . import services
from .models import VehicleAccess
from .selectors import vehicle_for, vehicles_for
from .serializers import (
    AccessInput,
    AccessSerializer,
    AccessUpdate,
    TransferInput,
    VehicleFilters,
    VehicleInput,
    VehicleSerializer,
)


def vehicle_response(request, vehicle, status=200):
    response = Response(VehicleSerializer(vehicle, context={"request": request}).data, status=status)
    response["ETag"] = services.etag(vehicle)
    return response


def access_response(grant, status=200):
    response = Response(AccessSerializer(grant).data, status=status)
    response["ETag"] = services.etag(grant)
    return response


class VehiclesView(APIView):
    default_status = "active"

    @extend_schema(parameters=[VehicleFilters], responses=VehicleSerializer(many=True))
    def get(self, request):
        filters = validated(VehicleFilters, request.query_params.dict())
        queryset = vehicles_for(request.user)
        status = filters.get("status", self.default_status)
        if status != "all":
            queryset = queryset.filter(status=status.upper())
        paginator = Pagination()
        return paginator.get_paginated_response(
            VehicleSerializer(
                paginator.paginate_queryset(queryset, request), many=True, context={"request": request}
            ).data
        )

    @extend_schema(request=VehicleInput, responses={201: VehicleSerializer})
    def post(self, request):
        return vehicle_response(
            request, services.create_vehicle(request, validated(VehicleInput, request.data)), 201
        )


class AdminVehiclesView(VehiclesView):
    permission_classes = [Administrator]
    default_status = "all"
    http_method_names = ["get", "head", "options"]


class VehicleDetailView(APIView):
    @extend_schema(responses=VehicleSerializer)
    def get(self, request, vehicle_id):
        return vehicle_response(request, vehicle_for(request.user, vehicle_id))

    @extend_schema(request=VehicleInput, responses=VehicleSerializer)
    def patch(self, request, vehicle_id):
        serializer = VehicleInput(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return vehicle_response(
            request, services.update_vehicle(request, vehicle_id, serializer.validated_data)
        )


class VehicleActionView(APIView):
    @extend_schema(request=None, responses=VehicleSerializer)
    def post(self, request, vehicle_id, action):
        # Také prázdná akce odmítá podvržená interní pole.
        from apps.core.serializers import StrictSerializer

        validated(StrictSerializer, request.data)
        return vehicle_response(request, services.archive_vehicle(request, vehicle_id, action == "archive"))


class AccessView(APIView):
    permission_classes = [Administrator]

    @method_decorator(transaction.atomic)
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, vehicle_id):
        vehicle = services.lock_vehicle(request, vehicle_id)
        grants = VehicleAccess.objects.filter(vehicle=vehicle).select_related("user")
        return Response(
            {
                "owner_id": str(vehicle.owner_id),
                "owner": {"username": vehicle.owner.username, "display_name": vehicle.owner.display_name},
                "results": AccessSerializer(grants, many=True).data,
            }
        )

    @extend_schema(request=AccessInput, responses={201: AccessSerializer})
    def post(self, request, vehicle_id):
        return access_response(
            services.create_access(request, vehicle_id, validated(AccessInput, request.data)), 201
        )


class AccessDetailView(APIView):
    permission_classes = [Administrator]

    @extend_schema(responses=AccessSerializer)
    def get(self, request, access_id):
        return access_response(get_object_or_404(VehicleAccess.objects.select_related("user"), pk=access_id))

    @extend_schema(request=AccessUpdate, responses=AccessSerializer)
    def patch(self, request, access_id):
        return access_response(
            services.change_access(request, access_id, validated(AccessUpdate, request.data))
        )

    @extend_schema(responses={204: None})
    def delete(self, request, access_id):
        services.change_access(request, access_id)
        return Response(status=204)


class TransferView(APIView):
    permission_classes = [Administrator]

    @extend_schema(request=TransferInput, responses=VehicleSerializer)
    def post(self, request, vehicle_id):
        return vehicle_response(
            request, services.transfer_owner(request, vehicle_id, validated(TransferInput, request.data))
        )
