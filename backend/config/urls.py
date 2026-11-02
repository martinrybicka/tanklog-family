from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView
from rest_framework.renderers import JSONRenderer

from apps.accounts import views
from apps.accounts.permissions import Administrator

handler400 = "apps.core.errors.bad_request"
handler404 = "apps.core.errors.not_found"
handler500 = "apps.core.errors.server_error"

urlpatterns = [
    path("api/v1/", include("apps.analytics.urls")),
    path("api/v1/", include("apps.refuelings.urls")),
    path("api/v1/", include("apps.vehicles.urls")),
    path("api/health/live/", views.live),
    path("api/health/ready/", views.ready),
    path("api/v1/auth/csrf/", views.CsrfView.as_view()),
    path("api/v1/auth/login/", views.LoginView.as_view()),
    path("api/v1/auth/logout/", views.LogoutView.as_view()),
    path("api/v1/auth/me/", views.MeView.as_view()),
    path("api/v1/auth/password/change/", views.PasswordChangeView.as_view()),
    path("api/v1/profile/", views.ProfileView.as_view()),
    path("api/v1/admin/users/", views.UsersView.as_view()),
    path("api/v1/admin/users/<uuid:user_id>/", views.UserDetailView.as_view()),
    path(
        "api/v1/admin/users/<uuid:user_id>/deactivate/",
        views.UserActionView.as_view(),
        {"action": "deactivate"},
    ),
    path(
        "api/v1/admin/users/<uuid:user_id>/activate/", views.UserActionView.as_view(), {"action": "activate"}
    ),
    path(
        "api/v1/admin/users/<uuid:user_id>/password-reset/",
        views.UserActionView.as_view(),
        {"action": "password-reset"},
    ),
    path("api/v1/admin/system/", views.SystemView.as_view()),
    path("api/v1/admin/audit/", views.AuditView.as_view()),
    path(
        "api/v1/admin/schema/",
        SpectacularAPIView.as_view(permission_classes=[Administrator], renderer_classes=[JSONRenderer]),
    ),
]
