from django.urls import path

from . import views

urlpatterns = [
    path("settings/", views.PreferenceView.as_view()),
    path("admin/settings/<uuid:user_id>/", views.AdminPreferenceView.as_view()),
    path("receipts/", views.DraftsView.as_view()),
    path("receipts/<uuid:draft_id>/", views.DraftView.as_view()),
    path("receipts/<uuid:draft_id>/image/", views.ImageView.as_view()),
    path("receipts/<uuid:draft_id>/recognize/", views.RecognizeView.as_view()),
    path("receipts/<uuid:draft_id>/complete/", views.CompleteView.as_view()),
]
