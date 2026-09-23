from django import forms

from .models import Staff, StaffDocument


class StaffForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = [
            "employee_code",
            "first_name",
            "middle_name",
            "last_name",
            "photograph",
            "gender",
            "date_of_birth",
            "phone",
            "email",
            "address",
            "department",
            "designation",
            "is_teacher",
            "joining_date",
            "status",
            "salary",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "joining_date": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["is_teacher"].widget.attrs["class"] = "form-check-input"


class StaffDocumentForm(forms.ModelForm):
    class Meta:
        model = StaffDocument
        fields = ["title", "document_type", "file", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["file"].widget.attrs["class"] = "form-control"