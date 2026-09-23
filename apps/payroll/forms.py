import calendar
import datetime

from django import forms

from .models import SalaryComponent


class PayrollRunForm(forms.Form):
    """Criteria for a new (or re-)processed monthly run."""

    month = forms.ChoiceField(
        choices=[(str(m), calendar.month_name[m]) for m in range(1, 13)]
    )
    year = forms.IntegerField(
        initial=datetime.date.today().year, min_value=2000, max_value=2100
    )
    draft = forms.BooleanField(
        required=False, initial=False, label="Create as draft (skip processing)"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "draft":
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs.setdefault("class", "form-control form-control-sm")


class SalaryComponentForm(forms.ModelForm):
    """Allowance / deduction component (fixed or % of basic)."""

    class Meta:
        model = SalaryComponent
        fields = [
            "name",
            "kind",
            "amount",
            "percentage",
            "applies_to",
            "is_taxable",
            "active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("amount") and not cleaned.get("percentage"):
            raise forms.ValidationError("Set either a fixed amount or a percentage.")
        return cleaned