from django import forms

from .models import AdmissionDocument, AdmissionInquiry


class AdmissionInquiryForm(forms.ModelForm):
    class Meta:
        model = AdmissionInquiry
        fields = [
            "student_first_name",
            "student_last_name",
            "date_of_birth",
            "gender",
            "klass",
            "guardian_name",
            "guardian_phone",
            "guardian_email",
            "previous_school",
            "address",
            "medical_notes",
            "applied_on",
            "interview_date",
            "test_score",
            "interview_notes",
            "notes",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "applied_on": forms.DateInput(attrs={"type": "date"}),
            "interview_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "address": forms.Textarea(attrs={"rows": 2}),
            "medical_notes": forms.Textarea(attrs={"rows": 2}),
            "interview_notes": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["gender"].widget.attrs["class"] = "form-select"


class AdmissionDocumentForm(forms.ModelForm):
    class Meta:
        model = AdmissionDocument
        fields = ["doc_type", "file", "note"]
        widgets = {"note": forms.TextInput(attrs={"placeholder": "e.g. scanned copy"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["doc_type"].widget.attrs["class"] = "form-select"


class AdmissionDecisionForm(forms.Form):
    """Approve or reject an application (spec §7 approval/rejection)."""

    DECISION_CHOICES = [
        ("accept", "Accept — move to Offered"),
        ("reject", "Reject"),
    ]
    decision = forms.ChoiceField(choices=DECISION_CHOICES, widget=forms.RadioSelect)
    interview_date = forms.DateTimeField(
        required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    test_score = forms.DecimalField(
        required=False, max_digits=5, decimal_places=2
    )
    interview_notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["decision"].widget.attrs["class"] = "form-check-input"


class EnrollmentForm(forms.Form):
    """Create the student record + fee setup + guardianship (§7)."""

    def __init__(self, *args, **kwargs):
        from apps.academics.models import Section

        klass_id = kwargs.pop("klass_id", None) or kwargs.get("initial", {}).get("klass_id")
        super().__init__(*args, **kwargs)
        if klass_id:
            self.fields["section"].queryset = Section.objects.filter(klass_id=klass_id)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["section"].widget.attrs["class"] = "form-select"
        self.fields["create_fee_voucher"].widget.attrs["class"] = "form-check-input"

    admission_number = forms.CharField(max_length=50)
    roll_number = forms.CharField(max_length=20, required=False)
    section = forms.ModelChoiceField(queryset=None, required=False)
    joined_at = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    create_fee_voucher = forms.BooleanField(
        required=False,
        initial=True,
        label="Generate fee voucher from active fee heads",
        help_text="Skips fee heads the student already has a voucher for.",
    )