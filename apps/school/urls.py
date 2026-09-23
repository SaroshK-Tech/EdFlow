from django.urls import path

from . import views

app_name = "school"

urlpatterns = [
    path("settings/", views.SchoolProfileView.as_view(), name="settings"),
    path("academic-years/add/", views.AcademicYearCreateView.as_view(), name="academic_year_add"),
    path("academic-years/<int:pk>/edit/", views.AcademicYearUpdateView.as_view(), name="academic_year_edit"),
    path("terms/add/", views.TermCreateView.as_view(), name="term_add"),
    path("terms/<int:pk>/edit/", views.TermUpdateView.as_view(), name="term_edit"),
    path("working-days/add/", views.WorkingDayCreateView.as_view(), name="working_day_add"),
    path("working-days/<int:pk>/delete/", views.WorkingDayDeleteView.as_view(), name="working_day_delete"),
    path("holidays/add/", views.HolidayCreateView.as_view(), name="holiday_add"),
    path("holidays/<int:pk>/edit/", views.HolidayUpdateView.as_view(), name="holiday_edit"),
    path("holidays/<int:pk>/delete/", views.HolidayDeleteView.as_view(), name="holiday_delete"),
]