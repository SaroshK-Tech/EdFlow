from django.urls import path

from . import views

app_name = "payroll"

urlpatterns = [
    path("", views.PayrollRunListView.as_view(), name="list"),
    path("run/", views.PayrollRunCreateView.as_view(), name="run"),
    path("reports/", views.PayrollReportsView.as_view(), name="reports"),
    path("components/", views.ComponentListView.as_view(), name="components"),
    path("components/add/", views.ComponentCreateView.as_view(), name="component_add"),
    path(
        "components/<int:pk>/edit/",
        views.ComponentUpdateView.as_view(),
        name="component_edit",
    ),
    path(
        "components/<int:pk>/delete/",
        views.ComponentDeleteView.as_view(),
        name="component_delete",
    ),
    path("staff/<int:pk>/slips/", views.StaffPayslipsView.as_view(), name="staff_slips"),
    path("<int:pk>/", views.PayrollRunDetailView.as_view(), name="detail"),
    path("<int:pk>/process/", views.PayrollRunProcessView.as_view(), name="process"),
    path("<int:pk>/pay/", views.PayrollRunPayView.as_view(), name="pay"),
    path("slip/<int:pk>/", views.PaySlipView.as_view(), name="slip"),
    path("slip/<int:pk>/pdf/", views.PaySlipPdfView.as_view(), name="slip_pdf"),
]