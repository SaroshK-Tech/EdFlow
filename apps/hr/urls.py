from django.urls import path

from . import views

app_name = "hr"

urlpatterns = [
    path("employees/", views.EmployeesView.as_view(), name="employees"),
    path("employees/<int:pk>/", views.EmployeeDetailView.as_view(), name="employee_detail"),
    path("employees/<int:pk>/edit/", views.EmployeeUpdateView.as_view(), name="employee_edit"),
    path(
        "qualifications/add/",
        views.QualificationCreateView.as_view(),
        name="qualification_add",
    ),
    path(
        "qualifications/<int:pk>/edit/",
        views.QualificationUpdateView.as_view(),
        name="qualification_edit",
    ),
    path(
        "qualifications/<int:pk>/delete/",
        views.QualificationDeleteView.as_view(),
        name="qualification_delete",
    ),
    path("experiences/add/", views.ExperienceCreateView.as_view(), name="experience_add"),
    path(
        "experiences/<int:pk>/edit/",
        views.ExperienceUpdateView.as_view(),
        name="experience_edit",
    ),
    path(
        "experiences/<int:pk>/delete/",
        views.ExperienceDeleteView.as_view(),
        name="experience_delete",
    ),
    path("designations/", views.DesignationListView.as_view(), name="designations"),
    path("designations/add/", views.DesignationCreateView.as_view(), name="designation_add"),
    path("designations/<int:pk>/edit/", views.DesignationUpdateView.as_view(), name="designation_edit"),
    path("designations/<int:pk>/delete/", views.DesignationDeleteView.as_view(), name="designation_delete"),
    path("leaves/", views.LeaveListView.as_view(), name="leaves"),
    path("leaves/add/", views.LeaveCreateView.as_view(), name="leave_add"),
    path("leaves/<int:pk>/edit/", views.LeaveUpdateView.as_view(), name="leave_edit"),
    path("leaves/<int:pk>/status/<str:action>/", views.leave_request_status, name="leave_status"),
    path("leave-balances/", views.LeaveBalancesView.as_view(), name="leave_balances"),
    path("staff-attendance/", views.StaffAttendanceView.as_view(), name="staff_attendance"),
    path("departments/add/", views.DepartmentCreateView.as_view(), name="department_add"),
    path("departments/<int:pk>/", views.DepartmentUpdateView.as_view(), name="department_edit"),
]