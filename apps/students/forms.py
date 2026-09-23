from django import forms

from .models import Student


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            "admission_number",
            "registration_number",
            "roll_number",
            "first_name",
            "middle_name",
            "last_name",
            "photograph",
            "date_of_birth",
            "gender",
            "blood_group",
            "religion",
            "nationality",
            "phone",
            "email",
            "address",
            "house",
            "klass",
            "section",
            "status",
            "previous_school",
            "medical_notes",
            "remarks",
            "joined_at",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "joined_at": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 2}),
            "medical_notes": forms.Textarea(attrs={"rows": 2}),
            "remarks": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit section choices to the selected class where possible.
        if self.instance and self.instance.klass_id:
            self.fields["section"].queryset = self.instance.klass.sections.all()
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["photograph"].widget.attrs["class"] = "form-control"


class StudentImportForm(forms.Form):
    """CSV upload for bulk student import (spec §5 'import')."""

    csv_file = forms.FileField(
        label="CSV file",
        help_text=(
            "Headers: Admission No, First Name, Last Name, Gender, Class, "
            "Section, Date of Birth, House, Phone, Email, Parent/Guardian Name… "
            "Columns named like the export file are accepted. You can use the "
            "built-in CSV export as a template."
        ),
    )
    skip_guardians = forms.BooleanField(
        required=False,
        initial=False,
        label="Skip parent/guardian import",
        help_text="Do not create parent/guardian records from parent columns.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["csv_file"].widget.attrs.update(
            {"class": "form-control", "accept": ".csv"}
        )
        self.fields["skip_guardians"].widget.attrs["class"] = "form-check-input"