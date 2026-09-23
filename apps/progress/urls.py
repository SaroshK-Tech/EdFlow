from django.urls import path

from . import views

app_name = "progress"

urlpatterns = [
    path("", views.ProgressListView.as_view(), name="list"),
    path("add/", views.ProgressRecordCreateView.as_view(), name="add"),
    path("students/<int:student_pk>/", views.ProgressDetailView.as_view(), name="detail"),
    path("students/<int:student_pk>/pdf/", views.ProgressReportPdfView.as_view(), name="pdf"),
    path("records/student/<int:student_pk>/", views.ProgressRecordsView.as_view(), name="records"),
    path("records/<int:pk>/edit/", views.ProgressRecordUpdateView.as_view(), name="record_edit"),
    path("records/<int:pk>/delete/", views.ProgressRecordDeleteView.as_view(), name="record_delete"),
]