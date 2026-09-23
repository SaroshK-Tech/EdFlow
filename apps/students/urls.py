from django.urls import path

from . import views

app_name = "students"

urlpatterns = [
    path("", views.StudentListView.as_view(), name="list"),
    path("export.csv", views.export_students_csv, name="export_csv"),
    path("import/", views.StudentImportView.as_view(), name="import"),
    path("import/preview/", views.StudentImportPreviewView.as_view(), name="import_preview"),
    path("add/", views.StudentCreateView.as_view(), name="add"),
    path("<int:pk>/", views.StudentDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.StudentUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.StudentDeleteView.as_view(), name="delete"),
]