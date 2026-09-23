from django import forms

from apps.academics.models import Subject

from .models import Exam, ExamSubject, ExamType, GradeBoundary


class _StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


class GradeBoundaryForm(_StyledModelForm):
    class Meta:
        model = GradeBoundary
        fields = ["name", "min_percentage", "max_percentage", "gpa", "remark"]


class ExamTypeForm(_StyledModelForm):
    class Meta:
        model = ExamType
        fields = ["name", "weightage", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}


class ExamForm(_StyledModelForm):
    class Meta:
        model = Exam
        fields = [
            "name",
            "exam_type",
            "academic_year",
            "start_date",
            "end_date",
            "status",
            "remarks",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class ExamSubjectForm(_StyledModelForm):
    """Add one or more of a class's subjects to an exam at once."""

    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        label="Subjects",
    )

    class Meta:
        model = ExamSubject
        fields = ["klass", "max_marks", "pass_marks", "weightage"]
