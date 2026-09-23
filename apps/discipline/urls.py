from django.urls import path

from . import views

app_name = "discipline"

urlpatterns = [
    path("", views.IncidentListView.as_view(), name="list"),
    path("add/", views.IncidentCreateView.as_view(), name="add"),
    path("<int:pk>/", views.IncidentDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.IncidentUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.IncidentDeleteView.as_view(), name="delete"),
    path("incidents/<int:incident_pk>/followups/add/", views.FollowUpCreateView.as_view(), name="followup_add"),
    path("students/<int:student_pk>/", views.StudentDisciplineView.as_view(), name="student"),
    path("warnings/", views.WarningListView.as_view(), name="warnings"),
    path("warnings/add/", views.WarningCreateView.as_view(), name="warning_add"),
    path("actions/", views.ActionListView.as_view(), name="actions"),
    path("actions/add/", views.ActionCreateView.as_view(), name="action_add"),
    path("achievements/", views.AchievementListView.as_view(), name="achievements"),
    path("achievements/add/", views.AchievementCreateView.as_view(), name="achievement_add"),
    path("announcement/", views.EmergencyAnnouncementView.as_view(), name="announcement"),
]