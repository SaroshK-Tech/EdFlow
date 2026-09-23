from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import RoleForm, UserAdminChangeForm, UserAdminCreateForm
from .models import Role, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = UserAdminCreateForm
    form = UserAdminChangeForm
    list_display = (
        "username",
        "get_full_name",
        "role",
        "email",
        "phone",
        "is_active",
    )
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("username", "first_name", "last_name", "email", "phone")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("EdFlow profile", {"fields": ("role", "phone", "avatar")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("EdFlow profile", {"fields": ("role", "phone")}),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    form = RoleForm
    list_display = ("name", "key", "is_system")
    filter_horizontal = ("permissions",)