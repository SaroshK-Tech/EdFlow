from django import forms

from .models import ProgressRecord


class ProgressRecordForm(forms.ModelForm):
    score = forms.DecimalField(
        min_value=0, max_value=100, widget=forms.NumberInput(attrs={"step": "0.01"})
    )

    class Meta:
        model = ProgressRecord
        fields = ["student", "term", "year", "subject", "category", "score", "remark"]
        widgets = {"remark": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")