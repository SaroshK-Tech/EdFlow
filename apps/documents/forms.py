from django import forms

from .models import DocumentTemplate


def _decorate(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.Select):
            widget.attrs.setdefault("class", "form-select")
        elif isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "form-check-input")
        else:
            widget.attrs.setdefault("class", "form-control")
    return form


class DocumentTemplateForm(forms.ModelForm):
    class Meta:
        model = DocumentTemplate
        fields = ["doc_type", "name", "body", "is_active"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.is_system:
            self.fields["doc_type"].disabled = True
        _decorate(self)


class StudentGenerateForm(forms.Form):
    """Picker shared by student ID, admission letter, certificates."""

    student = forms.ModelChoiceField(
        queryset=None, empty_label="Choose a student…", label="Student"
    )

    def __init__(self, *args, **kwargs):
        from apps.students.models import Student

        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.exclude(status="left").order_by(
            "first_name"
        )
        _decorate(self)


class CertificateGenerateForm(StudentGenerateForm):
    CERT_TYPES = [
        ("bonafide_certificate", "Bonafide Certificate"),
        ("character_certificate", "Character Certificate"),
        ("leaving_certificate", "Leaving Certificate"),
    ]

    certificate_type = forms.ChoiceField(
        choices=CERT_TYPES, label="Certificate type"
    )
    purpose = forms.CharField(
        required=False,
        label="Purpose (bonafide only)",
        help_text="e.g. Passport application, bank loan",
    )


class StaffGenerateForm(forms.Form):
    staff = forms.ModelChoiceField(
        queryset=None, empty_label="Choose a staff member…", label="Staff"
    )

    def __init__(self, *args, **kwargs):
        from apps.staff.models import Staff

        super().__init__(*args, **kwargs)
        self.fields["staff"].queryset = Staff.objects.exclude(status="left").order_by(
            "first_name"
        )
        _decorate(self)


class ReceiptGenerateForm(forms.Form):
    payment = forms.ModelChoiceField(
        queryset=None, empty_label="Choose a payment / receipt…", label="Fee payment"
    )

    def __init__(self, *args, **kwargs):
        from apps.fees.models import FeePayment

        super().__init__(*args, **kwargs)
        self.fields["payment"].queryset = FeePayment.objects.select_related(
            "student", "fee_head"
        )
        _decorate(self)