from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Role(models.Model):
    """Granular role used for role-based access control (spec §4)."""

    key = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(
        "auth.Permission", related_name="roles", blank=True
    )
    is_system = models.BooleanField(
        default=False, help_text="System roles cannot be deleted."
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Role"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.name


SYSTEM_ROLES = [
    ("super_admin", "Super Administrator"),
    ("school_administrator", "School Administrator"),
    ("principal", "Principal"),
    ("vice_principal", "Vice Principal"),
    ("academic_coordinator", "Academic Coordinator"),
    ("teacher", "Teacher"),
    ("class_teacher", "Class Teacher"),
    ("accountant", "Accountant"),
    ("hr_manager", "HR Manager"),
    ("librarian", "Librarian"),
    ("transport_manager", "Transport Manager"),
    ("receptionist", "Receptionist"),
    ("admission_officer", "Admission Officer"),
    ("parent", "Parent"),
    ("student", "Student"),
    ("staff", "Staff"),
]


class User(AbstractUser):
    """EdFlow user.

    Uses Django's permission machinery (groups not required). ``role`` is
    reserved for the school RBAC roles above. Grant/deny access in code via
    ``has_perm`` (superuser bypasses all checks).
    """

    role = models.ForeignKey(
        Role, null=True, blank=True, on_delete=models.SET_NULL, related_name="users"
    )
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True)

    # Optional links to school records (all nullable).
    student = models.OneToOneField(
        "students.Student",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="auth_user",
    )
    parent = models.OneToOneField(
        "parents.Parent",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="auth_user",
    )
    staff = models.OneToOneField(
        "staff.Staff",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="auth_user",
    )

    class Meta:
        ordering = ["username"]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.get_full_name() or self.username


def create_system_roles():
    """Idempotent seed of the standard school roles (spec §4)."""
    from django.contrib.auth.models import Permission

    created = []
    for key, name in SYSTEM_ROLES:
        role, was_created = Role.objects.get_or_create(
            key=key, defaults={"name": name, "is_system": True}
        )
        if was_created:
            created.append(role)
    # Student role: audit permissions only as configured later by admins.
    return created


class LoginHistory(models.Model):
    """Authentication outcome trail for security review (spec §27 login history)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="login_history",
    )
    username_attempted = models.CharField(max_length=150, blank=True)
    succeeded = models.BooleanField(default=True)
    ip_address = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    login_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-login_at"]
        verbose_name = "Login History"
        verbose_name_plural = "Login History"

    def __str__(self):
        return f"{self.username_attempted} {'OK' if self.succeeded else 'FAIL'} @ {self.login_at:%Y-%m-%d %H:%M}"