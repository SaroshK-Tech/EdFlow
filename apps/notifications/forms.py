from django import forms

from .models import Announcement, Audience, InboxMessage


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


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ["title", "body", "audience", "klass", "is_pinned", "is_emergency", "expires_at"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 4}),
            "expires_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}
            ),
        }

    def __init__(self, *args, **kwargs):
        from apps.academics.models import Class

        super().__init__(*args, **kwargs)
        classes = Class.objects.all()
        if classes.exists():
            self.fields["klass"].choices = [
                ("", "— no class —")
            ] + [(c.pk, c.name) for c in classes]
        else:
            self.fields["klass"].choices = [("", "No classes yet")]
        _decorate(self)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("audience") == Audience.CLASS and not cleaned.get("klass"):
            self.add_error("klass", "Choose a class for class announcements.")
        return cleaned


class InboxMessageForm(forms.ModelForm):
    class Meta:
        model = InboxMessage
        fields = ["recipient", "subject", "body", "is_important"]
        widgets = {
            "subject": forms.TextInput(attrs={"placeholder": "Subject"}),
            "body": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)