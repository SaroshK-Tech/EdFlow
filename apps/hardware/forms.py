from django import forms

from .models import Connection, Device, MaintenanceRequest


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


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = [
            "name",
            "device_type",
            "connection",
            "ip_address",
            "mac_address",
            "location",
            "model",
            "serial_number",
            "firmware_version",
            "sim_info",
            "network_status",
            "battery_level",
            "status",
            "notes",
            "installed_at",
        ]
        widgets = {
            "installed_at": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ip_address"].required = False
        _decorate(self)


class MaintenanceRequestForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRequest
        fields = [
            "device",
            "issue_title",
            "description",
            "priority",
            "status",
            "assigned_to",
            "resolution_notes",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "resolution_notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)
        self.fields["status"].required = False