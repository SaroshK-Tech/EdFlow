from django.contrib import messages
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    FormView,
    ListView,
    UpdateView,
)

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin

from .forms import RoleForm, UserCreateForm, UserUpdateForm
from .models import LoginHistory, Role, User

ADMIN_ROLE_KEYS = {
    "super_admin",
    "school_administrator",
    "principal",
    "vice_principal",
}


def _is_admin(user):
    return user.is_superuser or (user.role and user.role.key in ADMIN_ROLE_KEYS)


class AdminOnlyMixin:
    """Restrict the view to superusers or administrative roles (spec §4)."""

    def dispatch(self, request, *args, **kwargs):
        if not _is_admin(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class UserListView(AdminOnlyMixin, EdFlowMixin, SearchMixin, ListView):
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    paginate_by = 25
    page_title = "Users & Roles"
    page_subtitle = "Manage system accounts and role-based access control"
    active_page = "accounts"
    search_fields = [
        "username",
        "first_name",
        "last_name",
        "email",
        "phone",
        "role__name",
    ]
    search_placeholder = "Search users…"

    def get_queryset(self):
        return super().get_queryset().select_related("role").order_by("username")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["role_count"] = Role.objects.count()
        ctx["active_user_count"] = User.objects.filter(is_active=True).count()
        return ctx


class UserCreateView(AdminOnlyMixin, EdFlowMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "accounts/user_form.html"
    page_title = "Add User"
    page_subtitle = "Create a new system account"
    active_page = "accounts"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(
            self.request,
            f"accounts.user_create {self.object.username}",
            object_type="User",
            object_id=self.object.pk,
        )
        from apps.notifications.services import notify_user
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        admin_users = UserModel.objects.filter(
            is_superuser=True
        ) | UserModel.objects.filter(role__key__in=["super_admin", "school_administrator", "principal"])
        for admin in admin_users.distinct():
            if admin.pk != self.request.user.pk:
                notify_user(
                    admin,
                    f"New user created: {self.object.username}",
                    reverse("accounts:user_list"),
                    "person-plus",
                )
        messages.success(self.request, f"User {self.object.username} created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("accounts:user_list")


class UserUpdateView(AdminOnlyMixin, EdFlowMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "accounts/user_form.html"
    context_object_name = "user_obj"
    page_title = "Edit User"
    page_subtitle = "Update account details and access"
    active_page = "accounts"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(
            self.request,
            f"accounts.user_update {self.object.username}",
            object_type="User",
            object_id=self.object.pk,
        )
        messages.success(self.request, "User updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("accounts:user_list")


class UserToggleActiveView(AdminOnlyMixin, EdFlowMixin, UpdateView):
    """Activate / deactivate a user account (spec §27)."""

    model = User

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        if user == request.user:
            messages.error(request, "You cannot deactivate your own account.")
            return redirect("accounts:user_list")
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        state = "activated" if user.is_active else "deactivated"
        audit(
            request,
            f"accounts.user_{state} {user.username}",
            object_type="User",
            object_id=user.pk,
        )
        messages.success(request, f"User {user.username} {state}.")
        return redirect("accounts:user_list")


class UserResetPasswordView(AdminOnlyMixin, EdFlowMixin, FormView):
    """Admin-initiated (offline) password reset for a user (spec §27)."""

    form_class = SetPasswordForm
    template_name = "accounts/user_reset_password.html"
    page_title = "Reset Password"
    page_subtitle = "Set a new password on behalf of a user"
    active_page = "accounts"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.target = self.get_object()
        kwargs["user"] = self.target
        return kwargs

    def get_object(self):
        from django.shortcuts import get_object_or_404

        return get_object_or_404(User, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["target_user"] = self.get_object()
        return ctx

    def form_valid(self, form):
        form.save()
        audit(
            self.request,
            f"accounts.password_reset {self.get_object().username}",
            object_type="User",
            object_id=self.get_object().pk,
        )
        messages.success(
            self.request,
            f"Password reset for {self.get_object().username}.",
        )
        return redirect(reverse("accounts:user_list"))

    def get_success_url(self):
        return reverse("accounts:user_list")


class LoginHistoryListView(AdminOnlyMixin, EdFlowMixin, SearchMixin, ListView):
    model = LoginHistory
    template_name = "accounts/login_history.html"
    context_object_name = "logins"
    paginate_by = 40
    page_title = "Login History"
    page_subtitle = "Successful and failed authentication attempts"
    active_page = "accounts"
    search_fields = ["username_attempted", "ip_address"]
    search_placeholder = "Search by username or IP…"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("user")
            .order_by("-login_at")
        )


class RoleListView(AdminOnlyMixin, EdFlowMixin, SearchMixin, ListView):
    model = Role
    template_name = "accounts/role_list.html"
    context_object_name = "roles"
    page_title = "Roles & Permissions"
    page_subtitle = "Role definitions used for access control"
    active_page = "accounts"
    search_fields = ["key", "name", "description"]
    search_placeholder = "Search roles…"

    def get_queryset(self):
        return super().get_queryset().annotate(user_count=Count("users"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for role in ctx["roles"]:
            role.permission_count = role.permissions.count()
        return ctx


class RoleCreateView(AdminOnlyMixin, EdFlowMixin, CreateView):
    model = Role
    form_class = RoleForm
    template_name = "accounts/role_form.html"
    page_title = "Add Role"
    page_subtitle = "Define a new role and its permissions"
    active_page = "accounts"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(
            self.request,
            f"accounts.role_create {self.object.key}",
            object_type="Role",
            object_id=self.object.pk,
        )
        messages.success(self.request, f"Role {self.object.name} created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("accounts:role_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["permission_groups"] = self.get_form().permission_groups()
        return ctx


class RoleUpdateView(AdminOnlyMixin, EdFlowMixin, UpdateView):
    model = Role
    form_class = RoleForm
    template_name = "accounts/role_form.html"
    context_object_name = "role"
    page_title = "Edit Role"
    page_subtitle = "Update role details and permissions"
    active_page = "accounts"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["permission_groups"] = self.get_form().permission_groups()
        return ctx

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(
            self.request,
            f"accounts.role_update {self.object.key}",
            object_type="Role",
            object_id=self.object.pk,
        )
        messages.success(self.request, "Role updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("accounts:role_list")


class RoleDeleteView(AdminOnlyMixin, EdFlowMixin, DeleteView):
    model = Role
    context_object_name = "role"

    def post(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system:
            messages.error(request, "System roles cannot be deleted.")
            return redirect("accounts:role_list")
        name = role.name
        role.delete()
        audit(
            request,
            f"accounts.role_delete {role.key}",
            object_type="Role",
            object_id=role.pk,
        )
        messages.success(request, f"Role {name} deleted.")
        return redirect(reverse("accounts:role_list"))