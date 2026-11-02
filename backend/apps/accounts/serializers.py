from rest_framework import serializers

from apps.core.serializers import StrictSerializer

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "display_name",
            "email",
            "system_role",
            "is_active",
            "theme",
            "must_change_password",
            "version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class LoginSerializer(StrictSerializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)


class SessionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    username = serializers.CharField()
    must_change_password = serializers.BooleanField()
    display_name = serializers.CharField(required=False, allow_blank=True)
    system_role = serializers.ChoiceField(choices=User.Role.choices, required=False)
    theme = serializers.ChoiceField(choices=User.Theme.choices, required=False)


class ProfileSerializer(StrictSerializer):
    display_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True)
    theme = serializers.ChoiceField(choices=User.Theme.choices, required=False)


class PasswordChangeSerializer(StrictSerializer):
    current_password = serializers.CharField(
        max_length=256, required=False, trim_whitespace=False, write_only=True
    )
    new_password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)


class ReauthenticateSerializer(StrictSerializer):
    current_password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)


class AdminCreateSerializer(ReauthenticateSerializer):
    username = serializers.CharField(max_length=150, validators=User._meta.get_field("username").validators)
    display_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True, default="")
    system_role = serializers.ChoiceField(choices=User.Role.choices, default=User.Role.USER)

    def validate_username(self, value):
        return value.lower()


class AdminUpdateSerializer(ProfileSerializer):
    # Motiv se mění v profilu, nikoli administrátorem za uživatele.
    theme = None
    system_role = serializers.ChoiceField(choices=User.Role.choices, required=False)
    current_password = serializers.CharField(
        max_length=256, required=False, trim_whitespace=False, write_only=True
    )


class UserFiltersSerializer(StrictSerializer):
    search = serializers.CharField(max_length=200, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    system_role = serializers.ChoiceField(choices=User.Role.choices, required=False)
    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False)


class AuditFiltersSerializer(StrictSerializer):
    action = serializers.CharField(max_length=60, required=False)
    entity_id = serializers.UUIDField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False)

    def validate(self, attrs):
        if attrs.get("date_from") and attrs.get("date_to") and attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError("Počáteční datum nesmí být později než koncové.")
        return attrs
