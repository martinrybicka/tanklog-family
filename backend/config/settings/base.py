import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = False
ALLOWED_HOSTS = [
    s.strip() for s in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if s.strip()
]
CSRF_TRUSTED_ORIGINS = [
    s.strip()
    for s in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8080").split(",")
    if s.strip()
]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "axes",
    "apps.accounts",
    "apps.audit",
    "apps.vehicles",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.ApiContextMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "tanklog"),
        "USER": os.environ.get("POSTGRES_USER", "tanklog"),
        "PASSWORD": os.environ["POSTGRES_PASSWORD"],
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"connect_timeout": 5},
    }
}
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "apps.accounts.authentication.AccountBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "cs"
TIME_ZONE = "Europe/Prague"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 12 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_FAILURE_VIEW = "apps.core.errors.csrf_failure"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
DATA_UPLOAD_MAX_MEMORY_SIZE = 256 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 50
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.VersionedSessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["apps.accounts.permissions.FullSession"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "apps.core.errors.exception_handler",
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.Pagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNICODE_JSON": True,
}
SPECTACULAR_SETTINGS = {
    "TITLE": "TankLog API",
    "DESCRIPTION": "Fáze 2 – účty, vozidla a sdílení",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {"VehicleAccessRoleEnum": [("VIEWER", "Čtenář"), ("CONTRIBUTOR", "Přispěvatel")]},
}
AXES_HANDLER = "axes.handlers.database.AxesDatabaseHandler"
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_CALLABLE = "apps.core.errors.axes_lockout"
AXES_ENABLE_ACCESS_FAILURE_LOG = False
AXES_ENABLE_ACCESS_LOG = False
# Vnitřní webová proxy tuto hlavičku vždy přepíše skutečně ověřenou adresou.
AXES_CLIENT_IP_CALLABLE = "apps.accounts.authentication.client_ip"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {"axes": {"handlers": ["console"], "level": "ERROR", "propagate": False}},
}
