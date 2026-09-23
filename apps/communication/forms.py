from django import forms

from .models import Channel, MessageTemplate, Priority


def _decorate(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.Select):
            widget.attrs.setdefault("class", "form-select")
        elif isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "form-check-input")
        else:
            widget.attrs.setdefault("class", "form-control")
    return form


class MessageTemplateForm(forms.ModelForm):
    class Meta:
        model = MessageTemplate
        fields = ["key", "name", "channel", "body", "is_active"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.is_system:
            self.fields["key"].disabled = True
        _decorate(self)


class ComposeForm(forms.Form):
    MODE_CHOICES = {
        "class": "All students of a class",
        "all_students": "All active students",
        "manual": "Manual phone numbers",
    }

    channel = forms.ChoiceField(choices=Channel.choices)
    to_whom = forms.ChoiceField(choices=MODE_CHOICES, label="Recipients")
    klass = forms.ChoiceField(required=False, label="Class")
    template = forms.ChoiceField(required=False, label="Use template")
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Leave blank when a template is selected. Placeholders like "
        "{student_name} are replaced per recipient.",
    )
    manual_numbers = forms.CharField(
        required=False,
        label="Phone numbers",
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "One per line, e.g. 0722 123 456 or Name, 0722 123 456"}
        ),
        help_text="Only used when recipients is 'Manual phone numbers'.",
    )
    priority = forms.ChoiceField(choices=Priority.choices)
    schedule_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Schedule date (optional)",
    )
    schedule_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}),
        label="Schedule time (optional)",
    )

    def __init__(self, *args, **kwargs):
        from apps.academics.models import Class
        from .models import MessageTemplate

        super().__init__(*args, **kwargs)
        classes = Class.objects.all()
        if classes.exists():
            self.fields["klass"].choices = [
                ("", "All classes")
            ] + [(c.pk, c.name) for c in classes]
        else:
            self.fields["klass"].choices = [("", "No classes yet")]
        templates = MessageTemplate.objects.filter(is_active=True)
        self.fields["template"].choices = [
            ("", "— no template —")
        ] + [(t.pk, t.name) for t in templates]
        _decorate(self)

    def clean(self):
        cleaned = super().clean()
        to_whom = cleaned.get("to_whom")
        klass = cleaned.get("klass")
        message = cleaned.get("message")
        template = cleaned.get("template")
        if to_whom == "class" and not klass:
            self.add_error("klass", "Choose a class for class recipients.")
        if not message and not template:
            self.add_error("message", "Write a message or pick a template.")
        schedule_date = cleaned.get("schedule_date")
        schedule_time = cleaned.get("schedule_time")
        if (schedule_date is not None) != (schedule_time is not None):
            self.add_error("schedule_time", "Provide both a date and a time to schedule.")
        return cleaned