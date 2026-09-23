from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("", views.attendance_list, name="list"),
    path("mark/", views.mark_attendance, name="mark"),
    path("period/", views.period_attendance, name="period"),
    path("staff/", views.staff_attendance, name="staff"),
    path("reports/", views.attendance_reports, name="reports"),
    path("total/", views.attendance_total, name="total"),
    path("export/", views.export_attendance, name="export"),
]
