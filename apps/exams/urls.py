from django.urls import path

from . import views

app_name = "exams"

urlpatterns = [
    path("", views.ExamListView.as_view(), name="list"),
    path("add/", views.ExamCreateView.as_view(), name="add"),
    # Exam settings
    path("settings/grades/", views.GradeBoundaryListView.as_view(), name="gradeboundaries"),
    path("settings/grades/add/", views.GradeBoundaryCreateView.as_view(), name="gradeboundary_add"),
    path("settings/grades/<int:pk>/edit/", views.GradeBoundaryUpdateView.as_view(), name="gradeboundary_edit"),
    path("settings/grades/<int:pk>/delete/", views.GradeBoundaryDeleteView.as_view(), name="gradeboundary_delete"),
    path("settings/types/", views.ExamTypeListView.as_view(), name="examtypes"),
    path("settings/types/add/", views.ExamTypeCreateView.as_view(), name="examtype_add"),
    path("settings/types/<int:pk>/edit/", views.ExamTypeUpdateView.as_view(), name="examtype_edit"),
    path("settings/types/<int:pk>/delete/", views.ExamTypeDeleteView.as_view(), name="examtype_delete"),
    # Exam detail / CRUD
    path("<int:pk>/", views.ExamDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.ExamUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.ExamDeleteView.as_view(), name="delete"),
    path("<int:pk>/status/<str:status>/", views.exam_set_status, name="status"),
    # Subjects + marks
    path("<int:pk>/subjects/add/", views.ExamSubjectCreateView.as_view(), name="subject_add"),
    path("subjects/<int:pk>/remove/", views.ExamSubjectDeleteView.as_view(), name="subject_delete"),
    path("subjects/<int:pk>/marks/", views.marks_entry, name="marks_entry"),
]
