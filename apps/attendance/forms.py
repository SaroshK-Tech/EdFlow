import datetime

from django import forms

from apps.academics.models import Class, Section


class AttendanceSelectorForm(forms.Form):
    """Pick date + class (+ optional section) to mark attendance for."""

    date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), initial=datetime.date.today
    )
    klass = forms.ModelChoiceField(queryset=Class.objects.all(), label="Class")
    section = forms.ModelChoiceField(
        queryset=Section.objects.all(), required=False, label="Section", empty_label="All sections"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["section"].widget.attrs["class"] = "form-control"