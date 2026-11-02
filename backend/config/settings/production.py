import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, SECRET_KEY

if os.environ.get("DJANGO_DEBUG", "false").lower() != "false":
    raise ImproperlyConfigured("Produkční DEBUG musí být false.")
if os.environ.get("DJANGO_SECURE_COOKIES", "true").lower() != "true":
    raise ImproperlyConfigured("Produkční cookies musí být Secure.")
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 8:
    raise ImproperlyConfigured("Produkční SECRET_KEY musí být silná náhodná hodnota.")
if not ALLOWED_HOSTS or any("*" in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Produkční ALLOWED_HOSTS musí být konkrétní.")
if not CSRF_TRUSTED_ORIGINS or any(
    not origin.startswith("https://") or "*" in origin for origin in CSRF_TRUSTED_ORIGINS
):
    raise ImproperlyConfigured("Produkční CSRF originy musí být konkrétní HTTPS adresy.")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^api/health/(live|ready)/$"]
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
