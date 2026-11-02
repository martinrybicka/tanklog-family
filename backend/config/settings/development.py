import os

from .base import *  # noqa: F403

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
