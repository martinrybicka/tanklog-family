from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view()),
    path("vehicles/<uuid:vehicle_id>/statistics/", views.DashboardView.as_view()),
    path("vehicles/<uuid:vehicle_id>/consumption-intervals/", views.IntervalsView.as_view()),
    path("vehicles/<uuid:vehicle_id>/consumption-intervals/detail/", views.IntervalDetailView.as_view()),
]
