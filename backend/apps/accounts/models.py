import uuid

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower


class UserManager(DjangoUserManager):
    def _create_user(self, username, email, password, **extra_fields):
        return super()._create_user(username.strip().lower(), email, password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields["system_role"] = "ADMIN"
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrátor"
        USER = "USER", "Uživatel"

    class Theme(models.TextChoices):
        SYSTEM = "SYSTEM", "Podle systému"
        LIGHT = "LIGHT", "Světlý"
        DARK = "DARK", "Tmavý"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[
            RegexValidator(
                r"^[a-zA-Z0-9_.@+-]+$", "Použijte písmena bez diakritiky, číslice nebo znaky . @ + - _."
            )
        ],
    )
    display_name = models.CharField(max_length=150, blank=True)
    system_role = models.CharField(max_length=5, choices=Role, default=Role.USER)
    must_change_password = models.BooleanField(default=False)
    temporary_password_expires_at = models.DateTimeField(null=True, blank=True)
    temporary_password_consumed_at = models.DateTimeField(null=True, blank=True)
    auth_epoch = models.PositiveBigIntegerField(default=0)
    theme = models.CharField(max_length=6, choices=Theme, default=Theme.SYSTEM)
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    class Meta:
        constraints = [models.UniqueConstraint(Lower("username"), name="accounts_username_ci_unique")]
        ordering = ["username"]


class Installation(models.Model):
    """Trvalý jednorázový zámek úvodního nastavení; smazání účtů ho neotevře."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    completed_at = models.DateTimeField()

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_installation")]
