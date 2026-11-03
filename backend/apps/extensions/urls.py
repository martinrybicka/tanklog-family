from django.urls import path

from . import views

urlpatterns = [
    path("vehicles/<uuid:vehicle_id>/events/", views.EventsView.as_view()),
    path(
        "vehicles/<uuid:vehicle_id>/events/<uuid:event_id>/",
        views.EventDetailView.as_view(),
    ),
    path("vehicles/<uuid:vehicle_id>/energy-totals/", views.EnergyTotalsView.as_view()),
    path("vehicles/<uuid:vehicle_id>/imports/", views.ImportView.as_view()),
    path("imports/<uuid:batch_id>/", views.ImportDetailView.as_view()),
    path("reminders/", views.ReminderView.as_view()),
    path("vehicle-lookups/", views.LookupView.as_view()),
    path("vehicles/<uuid:vehicle_id>/photo-search/", views.PhotoSearchView.as_view()),
    path("vehicles/<uuid:vehicle_id>/photo/", views.PhotoSelectView.as_view()),
    path("vehicle-images/<uuid:image_id>/", views.PhotoContentView.as_view()),
    path("refuelings/<uuid:item_id>/recognize/", views.OcrView.as_view()),
    path(
        "refuelings/<uuid:item_id>/extractions/<uuid:extraction_id>/",
        views.ExtractionView.as_view(),
    ),
]
