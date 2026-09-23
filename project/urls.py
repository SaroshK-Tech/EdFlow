"""
Root URL configuration for EdFlow By AlgoriSync.

Each local app is mounted at a stable prefix and contributes its own
``urls.py`` (namespace = app name). See the spec's module list.
"""

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path(f"{settings.ADMIN_URL}/", admin.site.urls),
    path("", include("apps.core.urls", namespace="core")),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("school/", include("apps.school.urls", namespace="school")),
    path("students/", include("apps.students.urls", namespace="students")),
    path("parents/", include("apps.parents.urls", namespace="parents")),
    path("admissions/", include("apps.admissions.urls", namespace="admissions")),
    path("academics/", include("apps.academics.urls", namespace="academics")),
    path("timetable/", include("apps.timetable.urls", namespace="timetable")),
    path("attendance/", include("apps.attendance.urls", namespace="attendance")),
    path("staff/", include("apps.staff.urls", namespace="staff")),
    path("hr/", include("apps.hr.urls", namespace="hr")),
    path("payroll/", include("apps.payroll.urls", namespace="payroll")),
    path("houses/", include("apps.houses.urls", namespace="houses")),
    path("exams/", include("apps.exams.urls", namespace="exams")),
    path("results/", include("apps.results.urls", namespace="results")),
    path("progress/", include("apps.progress.urls", namespace="progress")),
    path("fees/", include("apps.fees.urls", namespace="fees")),
    path("finance/", include("apps.finance.urls", namespace="finance")),
    path("transport/", include("apps.transport.urls", namespace="transport")),
    path("library/", include("apps.library.urls", namespace="library")),
    path("inventory/", include("apps.inventory.urls", namespace="inventory")),
    path("discipline/", include("apps.discipline.urls", namespace="discipline")),
    path("communication/", include("apps.communication.urls", namespace="communication")),
    path("documents/", include("apps.documents.urls", namespace="documents")),
    path("reports/", include("apps.reports.urls", namespace="reports")),
    path("notifications/", include("apps.notifications.urls", namespace="notifications")),
    path("backup/", include("apps.backup.urls", namespace="backup")),
    path("hardware/", include("apps.hardware.urls", namespace="hardware")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)