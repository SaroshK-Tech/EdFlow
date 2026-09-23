from django import forms

from apps.students.models import Student

from .models import (
    Class,
    Homework,
    Room,
    Section,
    Subject,
    SubjectAllocation,
    Submission,
    Syllabus,
)


class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ["name", "level", "class_teacher", "subjects"]
        widgets = {"subjects": forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["subjects"].widget.attrs["class"] = "form-check-input"


class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ["klass", "name", "room"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ["name", "code"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ["name", "capacity", "room_type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class SubjectAllocationForm(forms.ModelForm):
    class Meta:
        model = SubjectAllocation
        fields = ["klass", "section", "subject", "teacher", "periods_per_week", "requires_lab"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class HomeworkForm(forms.ModelForm):
    """Homework/assignment form; teacher is preset for teacher accounts."""

    class Meta:
        model = Homework
        fields = [
            "title",
            "kind",
            "klass",
            "section",
            "subject",
            "teacher",
            "due_date",
            "description",
            "attachments",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        if self.user and getattr(self.user, "staff", None):
            self.fields.pop("teacher")

    def clean_section(self):
        klass = self.cleaned_data.get("klass")
        section = self.cleaned_data.get("section")
        if section and section.klass_id != getattr(klass, "pk", None):
            raise forms.ValidationError("Section does not belong to the selected class.")
        return section


class SubmissionForm(forms.ModelForm):
    """Student submission for a homework; student preset via linked account."""

    student = forms.ModelChoiceField(
        queryset=Student.objects.none(), required=False, label="Student"
    )

    class Meta:
        model = Submission
        fields = ["student", "content", "attachment"]
        widgets = {"content": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        students = kwargs.pop("students", Student.objects.none())
        hide_student = kwargs.pop("hide_student", False)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["student"].queryset = students
        if hide_student:
            self.fields.pop("student")


class SubmissionGradeForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ["marks", "teacher_remark"]
        widgets = {"teacher_remark": forms.TextInput(attrs={"placeholder": "Remark…"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class SyllabusForm(forms.ModelForm):
    class Meta:
        model = Syllabus
        fields = ["klass", "subject", "term", "title", "units", "start_date", "end_date"]
        widgets = {
            "units": forms.Textarea(attrs={"rows": 3, "placeholder": "One topic per line"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_units(self):
        if self.cleaned_data.get("units") is None:
            return []
        if isinstance(self.cleaned_data["units"], list):
            return [u for u in self.cleaned_data["units"] if u]
        return [
            line.strip()
            for line in self.cleaned_data["units"].splitlines()
            if line.strip()
        ]