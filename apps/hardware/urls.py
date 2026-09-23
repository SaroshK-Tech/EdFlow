from django.urls import path

from . import views

app_name = "hardware"

urlpatterns = [
    path("", views.DeviceListView.as_view(), name="devices"),
    path("add/", views.DeviceCreateView.as_view(), name="device_add"),
    path("<int:pk>/", views.DeviceDetailView.as_view(), name="device_detail"),
    path("<int:pk>/edit/", views.DeviceUpdateView.as_view(), name="device_edit"),
    path("<int:pk>/delete/", views.DeviceDeleteView.as_view(), name="device_delete"),
    # Maintenance tickets
    path("maintenance/", views.MaintenanceListView.as_view(), name="maintenance"),
    path("maintenance/add/", views.MaintenanceCreateView.as_view(), name="maintenance_add"),
    path(
        "maintenance/<int:pk>/edit/",
        views.MaintenanceUpdateView.as_view(),
        name="maintenance_edit",
    ),
    path(
        "maintenance/<int:pk>/delete/",
        views.MaintenanceDeleteView.as_view(),
        name="maintenance_delete",
    ),
    # Android gateway heartbeat endpoint
    path("gateway/<str:token>/heartbeat/", views.device_heartbeat, name="heartbeat"),
]