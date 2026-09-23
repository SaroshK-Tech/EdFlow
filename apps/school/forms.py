from django import forms

from .models import AcademicYear, Holiday, SchoolProfile, Term, WorkingDay


class SchoolProfileForm(forms.ModelForm):
    class Meta:
        model = SchoolProfile
        fields = [
            "name",
            "tagline",
            "logo",
            "address",
            "phone",
            "email",
            "website",
            "established_year",
            "bank_holder",
            "bank_name",
            "bank_branch",
            "bank_account_number",
            "bank_ifsc",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "tagline": forms.TextInput(attrs={"class": "form-control"}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "website": forms.URLInput(attrs={"class": "form-control"}),
            "established_year": forms.NumberInput(attrs={"class": "form-control"}),
            "bank_holder": forms.TextInput(attrs={"class": "form-control"}),
            "bank_name": forms.TextInput(attrs={"class": "form-control"}),
            "bank_branch": forms.TextInput(attrs={"class": "form-control"}),
            "bank_account_number": forms.TextInput(attrs={"class": "form-control"}),
            "bank_ifsc": forms.TextInput(attrs={"class": "form-control"}),
        }


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ["name", "start_date", "end_date", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
        }


class TermForm(forms.ModelForm):
    class Meta:
        model = Term
        fields = ["name", "start_date", "end_date", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
        }


class WorkingDayForm(forms.ModelForm):
    class Meta:
        model = WorkingDay
        fields = ["academic_year", "weekday"]
        widgets = {
            "academic_year": forms.Select(attrs={"class": "form-select"}),
            "weekday": forms.Select(attrs={"class": "form-select"}),
        }


class HolidayForm(forms.ModelForm):
    class Meta:
        model = Holiday
        fields = ["academic_year", "name", "start_date", "end_date"]
        widgets = {
            "academic_year": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
        }