from django.urls import path

from . import views

app_name = "backup"

urlpatterns = [
    path("", views.BackupListView.as_view(), name="list"),
    path("add/", views.BackupProfileCreateView.as_view(), name="profile_add"),
    path("<int:pk>/edit/", views.BackupProfileUpdateView.as_view(), name="profile_edit"),
    path("<int:pk>/delete/", views.BackupProfileDeleteView.as_view(), name="profile_delete"),
    path("<int:pk>/run/", views.RunBackupView.as_view(), name="run"),
    path("history/", views.BackupHistoryView.as_view(), name="history"),
    path("history/<int:pk>/verify/", views.BackupVerifyView.as_view(), name="verify"),
    path("history/<int:pk>/delete/", views.BackupJobDeleteView.as_view(), name="job_delete"),
    path("history/<int:pk>/restore/", views.BackupRestoreView.as_view(), name="restore"),
]