import datetime

from django import forms

from apps.staff.models import Staff
from apps.students.models import Status

from .models import (
    Department,
    Designation,
    Experience,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    Qualification,
)


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "head_of_department"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class HRStaffForm(forms.ModelForm):
    """HR-facing staff profile editor (adds salary/designation/joining)."""

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


class DesignationForm(forms.ModelForm):
    class Meta:
        model = Designation
        fields = ["name", "department", "grade", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class LeaveRequestForm(forms.ModelForm):
    start_date = forms.DateField(
        initial=datetime.date.today, widget=forms.DateInput(attrs={"type": "date"})
    )
    end_date = forms.DateField(
        initial=datetime.date.today, widget=forms.DateInput(attrs={"type": "date"})
    )

    class Meta:
        model = LeaveRequest
        fields = ["staff", "leave_type", "start_date", "end_date", "reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["staff"].queryset = Staff.objects.filter(
            status=Status.ACTIVE
        ).order_by("first_name", "last_name")
        self.fields["leave_type"].queryset = LeaveType.objects.all()

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before the start date.")
        return cleaned


class LeaveBalanceForm(forms.ModelForm):
    class Meta:
        model = LeaveBalance
        fields = ["entitled", "used"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control form-control-sm")


class QualificationForm(forms.ModelForm):
    class Meta:
        model = Qualification
        fields = [
            "staff",
            "qualification",
            "institution",
            "year_completed",
            "grade",
            "is_certified",
            "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["staff"].queryset = Staff.objects.all().order_by("first_name", "last_name")
        self.fields["is_certified"].widget.attrs["class"] = "form-check-input"
        for name, field in self.fields.items():
            if name == "is_certified":
                continue
            field.widget.attrs.setdefault("class", "form-control")


class ExperienceForm(forms.ModelForm):
    class Meta:
        model = Experience
        fields = [
            "staff",
            "organisation",
            "job_title",
            "start_date",
            "end_date",
            "current",
            "description",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["staff"].queryset = Staff.objects.all().order_by("first_name", "last_name")
        self.fields["current"].widget.attrs["class"] = "form-check-input"
        for name, field in self.fields.items():
            if name == "current":
                continue
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        current = cleaned.get("current")
        if current and end:
            self.add_error("end_date", "A current role should not have an end date.")
        if not current and start and end and end < start:
            self.add_error("end_date", "End date cannot be before the start date.")
        return cleaned