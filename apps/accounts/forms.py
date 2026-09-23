import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django import forms

from .models import Role, SYSTEM_ROLES

logger = logging.getLogger(__name__)

User = get_user_model()


class UserAdminCreateForm(UserCreationForm):
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(), required=False, label="Role"
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone")


class UserAdminChangeForm(forms.ModelForm):
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(), required=False, label="Role"
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "is_active",
            "role",
        )


def role_choices():
    return [(key, name) for key, name in SYSTEM_ROLES]


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ("key", "name", "description", "permissions")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                continue
            field.widget.attrs.setdefault("class", "form-control")

    def permission_groups(self):
        """Permission checkboxes grouped by app for the role form template."""
        from django.contrib.auth.models import Permission

        selected = set()
        if self.instance.pk:
            selected = {
                pid for pid in self.instance.permissions.values_list("id", flat=True)
            }
        perms = Permission.objects.select_related("content_type").order_by(
            "content_type__app_label", "codename"
        )
        groups = {}
        for perm in perms:
            label = perm.content_type.app_label.replace("_", " ").title()
            groups.setdefault(label, []).append(
                {
                    "id": perm.id,
                    "name": perm.name,
                    "selected": perm.id in selected,
                }
            )
        return sorted(groups.items())


class UserCreateForm(forms.ModelForm):
    """Create a user with a password and role from the portal UI."""

    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "is_staff",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].required = False
        self.fields["is_staff"].widget.attrs.setdefault("class", "form-check-input")
        self.fields["is_active"].widget.attrs.setdefault("class", "form-check-input")
        self.fields["role"].widget.attrs.setdefault("class", "form-select")
        for field in self.fields.values():
            if field.widget.attrs.get("class") == "form-select":
                continue
            if "form-check-input" in field.widget.attrs.get("class", ""):
                continue
            field.widget.attrs.setdefault("class", "form-control")

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p1 != p2:
            raise forms.ValidationError("The two passwords do not match.")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserUpdateForm(forms.ModelForm):
    """Edit a user; passwords are only changed when both fields are filled."""

    password1 = forms.CharField(
        label="New password",
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm new password",
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "is_staff",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].required = False
        self.fields["role"].widget.attrs.setdefault("class", "form-select")
        self.fields["is_staff"].widget.attrs.setdefault("class", "form-check-input")
        self.fields["is_active"].widget.attrs.setdefault("class", "form-check-input")
        for field in self.fields.values():
            if field.widget.attrs.get("class") == "form-select":
                continue
            if "form-check-input" in field.widget.attrs.get("class", ""):
                continue
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 or p2:
            if not p1:
                self.add_error("password1", "Enter the new password.")
            if not p2:
                self.add_error("password2", "Confirm the new password.")
            if p1 and p1 != p2:
                raise forms.ValidationError("The two passwords do not match.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("password1"):
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user