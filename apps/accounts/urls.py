from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "accounts"

urlpatterns = [
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/add/", views.UserCreateView.as_view(), name="user_add"),
    path("users/<int:pk>/edit/", views.UserUpdateView.as_view(), name="user_edit"),
    path("users/<int:pk>/toggle/", views.UserToggleActiveView.as_view(), name="user_toggle"),
    path(
        "users/<int:pk>/reset-password/",
        views.UserResetPasswordView.as_view(),
        name="user_reset_password",
    ),
    path("login-history/", views.LoginHistoryListView.as_view(), name="login_history"),
    path("roles/", views.RoleListView.as_view(), name="role_list"),
    path("roles/add/", views.RoleCreateView.as_view(), name="role_add"),
    path("roles/<int:pk>/edit/", views.RoleUpdateView.as_view(), name="role_edit"),
    path("roles/<int:pk>/delete/", views.RoleDeleteView.as_view(), name="role_delete"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
        "password_change/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change.html"
        ),
        name="password_change",
    ),
    path(
        "password_change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html"
        ),
        name="password_change_done",
    ),
    # Password reset (offline-first): the admin-set reset above is the primary
    # flow; the email flow below works when SMTP is configured in .env.
    path(
        "password/reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password/reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]