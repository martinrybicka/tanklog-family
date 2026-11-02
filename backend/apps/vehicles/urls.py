from django.urls import path

from . import views

urlpatterns = [
    path("vehicles/", views.VehiclesView.as_view()),
    path("vehicles/<uuid:vehicle_id>/", views.VehicleDetailView.as_view()),
    path("vehicles/<uuid:vehicle_id>/archive/", views.VehicleActionView.as_view(), {"action": "archive"}),
    path("vehicles/<uuid:vehicle_id>/restore/", views.VehicleActionView.as_view(), {"action": "restore"}),
    path("admin/vehicles/", views.AdminVehiclesView.as_view()),
    path("admin/vehicles/<uuid:vehicle_id>/access/", views.AccessView.as_view()),
    path("admin/vehicles/<uuid:vehicle_id>/transfer-owner/", views.TransferView.as_view()),
    path("admin/vehicle-access/<uuid:access_id>/", views.AccessDetailView.as_view()),
]
