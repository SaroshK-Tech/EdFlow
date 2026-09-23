from django.urls import path

from . import exports, views

app_name = "reports"

urlpatterns = [
    path("", views.ReportCenterView.as_view(), name="list"),
    path("students/", views.StudentReportView.as_view(), name="students"),
    path("attendance/", views.AttendanceReportView.as_view(), name="attendance"),
    path("finance/", views.FinanceReportView.as_view(), name="finance"),
    path("defaulters/", views.DefaultersReportView.as_view(), name="defaulters"),
    path("export/students.xlsx", exports.students_xlsx, name="students_export_xlsx"),
    path("export/students.pdf", exports.students_pdf, name="students_export_pdf"),
    path("export/attendance.xlsx", exports.attendance_xlsx, name="attendance_export_xlsx"),
    path("export/attendance.pdf", exports.attendance_pdf, name="attendance_export_pdf"),
    path("export/finance.xlsx", exports.finance_xlsx, name="finance_export_xlsx"),
    path("export/finance.pdf", exports.finance_pdf, name="finance_export_pdf"),
    path("export/defaulters.xlsx", exports.defaulters_xlsx, name="defaulters_export_xlsx"),
    path("export/defaulters.pdf", exports.defaulters_pdf, name="defaulters_export_pdf"),
]