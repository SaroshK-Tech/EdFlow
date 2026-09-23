from django import forms

from .models import Parent


class ParentForm(forms.ModelForm):
    class Meta:
        model = Parent
        fields = [
            "first_name",
            "last_name",
            "relationship",
            "occupation",
            "phone",
            "whatsapp_number",
            "email",
            "address",
            "emergency_contact",
            "students",
            "is_primary",
            "user",
            "notes",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["students"].widget.attrs["class"] = "form-select"
        self.fields["is_primary"].widget.attrs["class"] = "form-check-input"
        self.fields["user"].widget.attrs["class"] = "form-select"
        self.fields["user"].required = False
        self.fields["user"].empty_label = "— No portal login —"