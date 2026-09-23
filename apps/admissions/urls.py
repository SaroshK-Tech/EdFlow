from django.urls import path

from . import views

app_name = "admissions"

urlpatterns = [
    path("", views.AdmissionListView.as_view(), name="list"),
    path("add/", views.AdmissionCreateView.as_view(), name="add"),
    path("reports/", views.AdmissionReportsView.as_view(), name="reports"),
    path("<int:pk>/", views.AdmissionDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.AdmissionUpdateView.as_view(), name="edit"),
    path("<int:pk>/decision/", views.AdmissionDecisionView.as_view(), name="decision"),
    path("<int:pk>/documents/add/", views.AdmissionDocumentCreateView.as_view(), name="document_add"),
    path("documents/<int:pk>/delete/", views.AdmissionDocumentDeleteView.as_view(), name="document_delete"),
    path("<int:pk>/enroll/", views.AdmissionEnrollView.as_view(), name="enroll"),
]