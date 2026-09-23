from django import forms

from apps.academics.models import Class, Period, Room, Subject
from apps.school.models import AcademicYear, Term, Weekday
from apps.staff.models import Staff


class GenerateTimetableForm(forms.Form):
    name = forms.CharField(
        label="Timetable name",
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "e.g. Term 1 Main Timetable"}),
    )
    academic_year = forms.ModelChoiceField(
        label="Academic year",
        queryset=AcademicYear.objects.all(),
        empty_label=None,
    )
    term = forms.ModelChoiceField(
        label="Term (optional)",
        queryset=Term.objects.all(),
        required=False,
    )
    classes = forms.ModelMultipleChoiceField(
        label="Classes to schedule",
        queryset=Class.objects.all(),
    )
    max_seconds = forms.IntegerField(
        label="Solver time budget (seconds)",
        min_value=1,
        max_value=300,
        initial=30,
        help_text="How long CP-SAT may search before returning its best result.",
    )
    note = forms.CharField(
        label="Note",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Optional note stored with the generated timetable."}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active = AcademicYear.objects.filter(is_active=True).first()
        if active:
            self.fields["academic_year"].initial = active.pk
            self.fields["term"].queryset = Term.objects.filter(academic_year=active)
            self.initial["classes"] = list(
                Class.objects.filter(subject_allocations__periods_per_week__gt=0)
                .values_list("pk", flat=True)
                .distinct()
            )


class CellEditForm(forms.Form):
    klass = forms.ModelChoiceField(queryset=Class.objects.all())
    weekday = forms.ChoiceField(choices=Weekday.choices)
    period = forms.ModelChoiceField(queryset=Period.objects.all())
    subject = forms.ModelChoiceField(queryset=Subject.objects.all())
    teacher = forms.ModelChoiceField(queryset=Staff.objects.filter(is_teacher=True))
    room = forms.ModelChoiceField(queryset=Room.objects.all())


class RegenerateTimetableForm(forms.Form):
    """Selective re-generation scope (spec §9: selected classes/teachers/days)."""

    max_seconds = forms.IntegerField(
        label="Solver time budget (seconds)",
        min_value=1,
        max_value=300,
        initial=30,
    )
    note = forms.CharField(
        label="Note",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Why is this being regenerated?"}),
    )

    def __init__(self, *args, **kwargs):
        default_seconds = kwargs.pop("default_seconds", 30)
        klass_id = kwargs.pop("klass_id", None)
        teacher_id = kwargs.pop("teacher_id", None)
        weekday = kwargs.pop("weekday", None)
        super().__init__(*args, **kwargs)
        self.fields["max_seconds"].initial = default_seconds
        self.fields["classes"] = forms.ModelMultipleChoiceField(
            label="Regenerate classes",
            queryset=Class.objects.all(),
            required=False,
        )
        self.fields["teachers"] = forms.ModelMultipleChoiceField(
            label="Regenerate teachers",
            queryset=Staff.objects.filter(is_teacher=True),
            required=False,
        )
        self.fields["days"] = forms.MultipleChoiceField(
            label="Regenerate days",
            choices=Weekday.choices,
            required=False,
            widget=forms.CheckboxSelectMultiple,
        )
        if klass_id:
            self.initial["classes"] = [klass_id]
        if teacher_id:
            self.initial["teachers"] = [teacher_id]
        if weekday:
            self.initial["days"] = [weekday]