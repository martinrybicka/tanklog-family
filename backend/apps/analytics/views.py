from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.views import validated
from apps.core.pagination import Pagination

from . import services
from .serializers import (
    DashboardOutput,
    IntervalDetailFilters,
    IntervalDetailOutput,
    IntervalFilters,
    IntervalPageOutput,
    StatisticsFilters,
)


class DashboardView(APIView):
    @extend_schema(parameters=[StatisticsFilters], responses=DashboardOutput)
    def get(self, request, vehicle_id=None):
        return Response(
            services.dashboard(request, validated(StatisticsFilters, request.query_params.dict()), vehicle_id)
        )


class IntervalsView(APIView):
    @extend_schema(parameters=[IntervalFilters], responses=IntervalPageOutput)
    def get(self, request, vehicle_id):
        data = services.intervals(
            request, validated(IntervalFilters, request.query_params.dict()), vehicle_id
        )
        paginator = Pagination()
        return paginator.get_paginated_response(paginator.paginate_queryset(data, request))


class IntervalDetailView(APIView):
    @extend_schema(parameters=[IntervalDetailFilters], responses=IntervalDetailOutput)
    def get(self, request, vehicle_id):
        return Response(
            services.intervals(
                request, validated(IntervalDetailFilters, request.query_params.dict()), vehicle_id, True
            )
        )
