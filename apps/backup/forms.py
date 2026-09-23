from django import forms

from .models import BackupProfile


class BackupProfileForm(forms.ModelForm):
    class Meta:
        model = BackupProfile
        fields = ["name", "destination_path", "keep_count", "is_active", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "destination_path": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "E:\\school_backups"}
            ),
            "keep_count": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notes": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
        }