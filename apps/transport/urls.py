from django.urls import path

from . import views

app_name = "transport"

urlpatterns = [
    path("", views.VehicleListView.as_view(), name="list"),
    path("vehicles/add/", views.VehicleCreateView.as_view(), name="vehicle_add"),
    path("vehicles/<int:pk>/edit/", views.VehicleUpdateView.as_view(), name="vehicle_edit"),
    path("vehicles/<int:pk>/delete/", views.VehicleDeleteView.as_view(), name="vehicle_delete"),
    path("routes/", views.RouteListView.as_view(), name="routes"),
    path("routes/add/", views.RouteCreateView.as_view(), name="route_add"),
    path("routes/<int:pk>/edit/", views.RouteUpdateView.as_view(), name="route_edit"),
    path("routes/<int:pk>/", views.RouteDetailView.as_view(), name="route_detail"),
    path("stops/", views.StopListView.as_view(), name="stops"),
    path("stops/add/", views.StopCreateView.as_view(), name="stop_add"),
    path("stops/<int:pk>/delete/", views.StopDeleteView.as_view(), name="stop_delete"),
    path("drivers/", views.DriverListView.as_view(), name="drivers"),
    path("drivers/add/", views.DriverCreateView.as_view(), name="driver_add"),
    path("drivers/<int:pk>/edit/", views.DriverUpdateView.as_view(), name="driver_edit"),
    path("assign/", views.TransportAssignView.as_view(), name="assign"),
    path("assign/<int:pk>/delete/", views.AssignmentDeleteView.as_view(), name="assignment_delete"),
    path("reports/", views.TransportReportsView.as_view(), name="reports"),
]