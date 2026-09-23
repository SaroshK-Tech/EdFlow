from django.urls import path

from . import views

app_name = "academics"

urlpatterns = [
    path("classes/", views.ClassListView.as_view(), name="classes"),
    path("classes/add/", views.ClassCreateView.as_view(), name="class_add"),
    path("classes/<int:pk>/edit/", views.ClassUpdateView.as_view(), name="class_edit"),
    path("sections/", views.SectionListView.as_view(), name="sections"),
    path("sections/add/", views.SectionCreateView.as_view(), name="section_add"),
    path("sections/<int:pk>/edit/", views.SectionUpdateView.as_view(), name="section_edit"),
    path("subjects/", views.SubjectListView.as_view(), name="subjects"),
    path("subjects/add/", views.SubjectCreateView.as_view(), name="subject_add"),
    path("subjects/<int:pk>/edit/", views.SubjectUpdateView.as_view(), name="subject_edit"),
    path("rooms/", views.RoomListView.as_view(), name="rooms"),
    path("rooms/add/", views.RoomCreateView.as_view(), name="room_add"),
    path("rooms/<int:pk>/edit/", views.RoomUpdateView.as_view(), name="room_edit"),
    # Homework & assignments (spec §19)
    path("homework/", views.HomeworkListView.as_view(), name="homework"),
    path("homework/add/", views.HomeworkCreateView.as_view(), name="homework_add"),
    path("homework/<int:pk>/", views.HomeworkDetailView.as_view(), name="homework_detail"),
    path("homework/<int:pk>/edit/", views.HomeworkUpdateView.as_view(), name="homework_edit"),
    path("homework/<int:pk>/delete/", views.HomeworkDeleteView.as_view(), name="homework_delete"),
    path("homework/<int:pk>/submit/", views.submission_submit, name="submission_add"),
    path("submissions/<int:pk>/grade/", views.submission_grade, name="submission_grade"),
    # Syllabus / curriculum (spec §8)
    path("syllabus/", views.SyllabusListView.as_view(), name="syllabus"),
    path("syllabus/add/", views.SyllabusCreateView.as_view(), name="syllabus_add"),
    path("syllabus/<int:pk>/edit/", views.SyllabusUpdateView.as_view(), name="syllabus_edit"),
    path("syllabus/<int:pk>/delete/", views.SyllabusDeleteView.as_view(), name="syllabus_delete"),
]