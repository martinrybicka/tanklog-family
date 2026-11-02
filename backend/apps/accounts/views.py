import django
from django.contrib.auth import logout
from django.db import connection
from django.db.models import Q
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditEvent, record
from apps.core.pagination import Pagination

from . import services
from .models import User
from .permissions import Administrator, SessionRequired
from .serializers import (
    AdminCreateSerializer,
    AdminUpdateSerializer,
    AuditFiltersSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    ProfileSerializer,
    ReauthenticateSerializer,
    SessionSerializer,
    UserFiltersSerializer,
    UserSerializer,
)


def user_response(user, status_code=200):
    response = Response(UserSerializer(user).data, status=status_code)
    response["ETag"] = services.etag(user)
    return response


def session_data(user):
    if user.must_change_password:
        return {"id": str(user.pk), "username": user.username, "must_change_password": True}
    return {
        "id": str(user.pk),
        "username": user.username,
        "display_name": user.display_name,
        "system_role": user.system_role,
        "must_change_password": False,
        "theme": user.theme,
    }


def validated(serializer_class, data):
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def temporary_response(user, password, status_code=200):
    response = Response(
        {
            "user_id": str(user.pk),
            "temporary_password": password,
            "expires_at": user.temporary_password_expires_at.isoformat(),
            "must_change_password": True,
        },
        status=status_code,
    )
    response["ETag"] = services.etag(user)
    return response


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response({"csrf_token": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=LoginSerializer, responses=SessionSerializer)
    def post(self, request):
        data = validated(LoginSerializer, request.data)
        user = services.sign_in(request._request, **data)
        return Response(session_data(user))


@method_decorator(csrf_protect, name="dispatch")
class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        if request._request.user.is_authenticated:
            record(request._request, "auth.logout", request._request.user)
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [SessionRequired]

    @extend_schema(responses=SessionSerializer)
    def get(self, request):
        return Response(session_data(request.user))


class ProfileView(APIView):
    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return user_response(request.user)

    @extend_schema(request=ProfileSerializer, responses=UserSerializer)
    def patch(self, request):
        return user_response(services.update_profile(request, validated(ProfileSerializer, request.data)))


class PasswordChangeView(APIView):
    permission_classes = [SessionRequired]

    @extend_schema(request=PasswordChangeSerializer, responses=UserSerializer)
    def post(self, request):
        return user_response(
            services.change_password(request, validated(PasswordChangeSerializer, request.data))
        )


class UsersView(APIView):
    permission_classes = [Administrator]

    @extend_schema(parameters=[UserFiltersSerializer], responses=UserSerializer(many=True))
    def get(self, request):
        filters = validated(UserFiltersSerializer, request.query_params.dict())
        users = User.objects.all()
        if filters.get("search"):
            users = users.filter(
                Q(username__icontains=filters["search"]) | Q(display_name__icontains=filters["search"])
            )
        for key in ("is_active", "system_role"):
            if key in filters:
                users = users.filter(**{key: filters[key]})
        paginator = Pagination()
        return paginator.get_paginated_response(
            UserSerializer(paginator.paginate_queryset(users, request), many=True).data
        )

    @extend_schema(request=AdminCreateSerializer, responses={201: OpenApiTypes.OBJECT})
    def post(self, request):
        user, password = services.create_account(request, validated(AdminCreateSerializer, request.data))
        return temporary_response(user, password, 201)


class UserDetailView(APIView):
    permission_classes = [Administrator]

    @extend_schema(responses=UserSerializer)
    def get(self, request, user_id):
        return user_response(get_object_or_404(User, pk=user_id))

    @extend_schema(request=AdminUpdateSerializer, responses=UserSerializer)
    def patch(self, request, user_id):
        return user_response(
            services.update_account(request, user_id, validated(AdminUpdateSerializer, request.data))
        )


class UserActionView(APIView):
    permission_classes = [Administrator]

    @extend_schema(request=ReauthenticateSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request, user_id, action):
        data = validated(ReauthenticateSerializer, request.data)
        user, password = services.account_action(request, user_id, action, data["current_password"])
        return temporary_response(user, password) if password else user_response(user)


class SystemView(APIView):
    permission_classes = [Administrator]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return Response(
            {
                "application": "TankLog",
                "version": "0.2.0",
                "phase": 2,
                "django_version": django.get_version(),
                "database": "ok",
            }
        )


class AuditSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.username", default=None)

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "occurred_at",
            "actor_name",
            "action",
            "entity_type",
            "entity_id",
            "vehicle_id",
            "request_id",
            "changes",
        ]


class AuditView(APIView):
    permission_classes = [Administrator]

    @extend_schema(parameters=[AuditFiltersSerializer], responses=AuditSerializer(many=True))
    def get(self, request):
        filters = validated(AuditFiltersSerializer, request.query_params.dict())
        events = AuditEvent.objects.select_related("actor")
        for key in ("action", "entity_id"):
            if key in filters:
                events = events.filter(**{key: filters[key]})
        if "date_from" in filters:
            events = events.filter(occurred_at__date__gte=filters["date_from"])
        if "date_to" in filters:
            events = events.filter(occurred_at__date__lte=filters["date_to"])
        paginator = Pagination()
        return paginator.get_paginated_response(
            AuditSerializer(paginator.paginate_queryset(events, request), many=True).data
        )


def live(request):
    return JsonResponse({"status": "ok"})


def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
