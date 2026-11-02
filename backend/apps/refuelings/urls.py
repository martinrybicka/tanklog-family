from django.urls import path

from . import views

urlpatterns = [
    path("refuelings/", views.RefuelingsView.as_view()),
    path("refuelings/export/", views.ExportView.as_view()),
    path("refuelings/<uuid:item_id>/", views.RefuelingDetailView.as_view()),
    path("refuelings/<uuid:item_id>/receipt/", views.ReceiptView.as_view()),
    path("vehicles/<uuid:vehicle_id>/refueling-order/", views.OrderView.as_view()),
    path("vehicles/<uuid:vehicle_id>/payer-options/", views.PayerOptionsView.as_view()),
]
