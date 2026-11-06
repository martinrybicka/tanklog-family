"""Jednorázové vytvoření prvního správce bez veřejné registrace."""

import secrets

from django.conf import settings
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection, transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import record
from apps.core.errors import Problem
from apps.core.serializers import StrictSerializer

from .models import Installation, User
from .services import start_session
from .views import session_data, validated


def available():
    return bool(
        len(settings.TANKLOG_SETUP_TOKEN) >= 32
        and not Installation.objects.exists()
        and not User.objects.exists()
    )


class BootstrapInput(StrictSerializer):
    setup_token = serializers.CharField(max_length=256, write_only=True, trim_whitespace=False)
    username = serializers.CharField(max_length=150, validators=User._meta.get_field("username").validators)
    display_name = serializers.CharField(max_length=150, allow_blank=True, default="")
    password = serializers.CharField(max_length=256, write_only=True, trim_whitespace=False)
    password_confirmation = serializers.CharField(max_length=256, write_only=True, trim_whitespace=False)


@method_decorator(csrf_protect, name="dispatch")
class BootstrapView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response({"available": available()})

    @extend_schema(request=BootstrapInput, responses=OpenApiTypes.OBJECT)
    @transaction.atomic
    def post(self, request):
        data = validated(BootstrapInput, request.data)
        # Tentýž zámek blokuje i souběžné běžné INSERTy, například createsuperuser.
        with connection.cursor() as cursor:
            cursor.execute("LOCK TABLE accounts_user IN SHARE ROW EXCLUSIVE MODE")
        if not available():
            raise Problem("setup_closed", "Úvodní nastavení již není dostupné.", 409)
        if not secrets.compare_digest(data["setup_token"], settings.TANKLOG_SETUP_TOKEN):
            raise Problem("invalid_setup_token", "Jednorázový instalační kód není platný.", 403)
        if data["password"] != data["password_confirmation"]:
            raise serializers.ValidationError({"password_confirmation": "Hesla se neshodují."})
        user = User(
            username=data["username"].strip().lower(),
            display_name=data["display_name"],
            system_role=User.Role.ADMIN,
        )
        try:
            password_validation.validate_password(data["password"], user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        user.set_password(data["password"])
        user.save()
        Installation.objects.create(completed_at=timezone.now())
        start_session(request._request, user)
        record(request, "installation.completed", user, actor=user)
        return Response(session_data(user), status=201)
