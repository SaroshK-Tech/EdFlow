import datetime

from django import forms

from apps.academics.models import Class
from apps.students.models import Student

from .models import (
    Achievement,
    Action,
    FollowUp,
    Incident,
    Warning,
)


class IncidentForm(forms.ModelForm):
    date = forms.DateField(
        initial=datetime.date.today, widget=forms.DateInput(attrs={"type": "date"})
    )

    class Meta:
        model = Incident
        fields = [
            "student",
            "klass",
            "date",
            "type",
            "title",
            "description",
            "severity",
            "status",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        student = cleaned.get("student")
        klass = cleaned.get("klass")
        if student and student.klass_id:
            cleaned["klass"] = klass or student.klass
        return cleaned


class WarningForm(forms.ModelForm):
    date = forms.DateField(
        initial=datetime.date.today, widget=forms.DateInput(attrs={"type": "date"})
    )

    class Meta:
        model = Warning
        fields = ["student", "incident", "date", "type", "details", "issued_by", "follow_up_required"]
        widgets = {"details": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class ActionForm(forms.ModelForm):
    date = forms.DateField(
        initial=datetime.date.today, widget=forms.DateInput(attrs={"type": "date"})
    )
    start_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    end_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    class Meta:
        model = Action
        fields = [
            "student",
            "date",
            "kind",
            "description",
            "start_date",
            "end_date",
            "completed",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class AchievementForm(forms.ModelForm):
    date = forms.DateField(
        initial=datetime.date.today, widget=forms.DateInput(attrs={"type": "date"})
    )

    class Meta:
        model = Achievement
        fields = ["student", "date", "category", "title", "description", "house_points"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class FollowUpForm(forms.ModelForm):
    due_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    class Meta:
        model = FollowUp
        fields = ["note", "due_date", "completed", "owner"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class EmergencyAnnouncementForm(forms.Form):
    title = forms.CharField(max_length=200)
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")