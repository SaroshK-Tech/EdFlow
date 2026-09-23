import datetime

from django import forms

from apps.academics.models import Class, Section

from .models import Concession, FeeHead, FeePayment, StudentConcession


class FeeHeadForm(forms.ModelForm):
    class Meta:
        model = FeeHead
        fields = ["name", "description", "amount", "is_recurring", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class FeePaymentForm(forms.ModelForm):
    paid_on = forms.DateField(
        initial=datetime.date.today, widget=forms.DateInput(attrs={"type": "date"})
    )

    class Meta:
        model = FeePayment
        fields = ["student", "fee_head", "amount", "discount", "method", "paid_on", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class VoucherGenerationForm(forms.Form):
    """Criteria for bulk-generating fee vouchers (spec §15 'student invoices')."""

    klass = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        label="Class",
        empty_label="Select a class…",
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.select_related("klass"),
        label="Section",
        required=False,
        empty_label="All sections",
    )
    fee_heads = forms.ModelMultipleChoiceField(
        queryset=FeeHead.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        label="Fee heads to bill",
    )
    due_date = forms.DateField(
        initial=datetime.date.today, widget=forms.DateInput(attrs={"type": "date"})
    )
    notes = forms.CharField(max_length=200, required=False, label="Note on voucher")
    skip_existing = forms.BooleanField(
        required=False,
        initial=True,
        label="Skip students who already have a voucher",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in ("fee_heads", "skip_existing"):
                continue
            field.widget.attrs.setdefault("class", "form-control")
        if not self.is_bound:
            self.fields["fee_heads"].initial = list(
                FeeHead.objects.filter(is_active=True).values_list("pk", flat=True)
            )

    def clean(self):
        cleaned = super().clean()
        klass = cleaned.get("klass")
        section = cleaned.get("section")
        if klass and section and section.klass_id != klass.pk:
            self.add_error("section", "Section does not belong to the selected class.")
        if not cleaned.get("fee_heads"):
            self.add_error("fee_heads", "Select at least one fee head.")
        return cleaned


class ConcessionForm(forms.ModelForm):
    """Create/edit a scholarship, concession or discount scheme."""

    class Meta:
        model = Concession
        fields = [
            "name",
            "concession_type",
            "description",
            "percentage",
            "flat_amount",
            "fee_heads",
            "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fee_heads"].queryset = FeeHead.objects.filter(is_active=True)
        self.fields["fee_heads"].widget.attrs["class"] = "form-select"
        self.fields["fee_heads"].help_text = (
            "Leave empty to apply to all fee heads on a voucher."
        )
        self.fields["is_active"].widget.attrs["class"] = "form-check-input"
        for name, field in self.fields.items():
            if name in ("is_active",):
                continue
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        percentage = cleaned.get("percentage")
        flat_amount = cleaned.get("flat_amount")
        if percentage and flat_amount:
            self.add_error(
                "percentage",
                "Choose either percentage or flat amount, not both.",
            )
        if not percentage and not flat_amount:
            self.add_error(
                "percentage",
                "Provide a percentage or a flat amount for this concession.",
            )
        return cleaned


class StudentConcessionForm(forms.ModelForm):
    """Assign a concession scheme to one student."""

    class Meta:
        model = StudentConcession
        fields = ["student", "concession", "starts_on", "ends_on", "is_active", "note"]
        widgets = {
            "starts_on": forms.DateInput(attrs={"type": "date"}),
            "ends_on": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["concession"].queryset = Concession.objects.filter(is_active=True)
        self.fields["is_active"].widget.attrs["class"] = "form-check-input"
        for name, field in self.fields.items():
            if name == "is_active":
                continue
            field.widget.attrs.setdefault("class", "form-control")
