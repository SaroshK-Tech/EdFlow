from django import forms

from .models import Driver, Route, Stop, TransportAssignment, Vehicle


class BaseFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")


class VehicleForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["registration_number", "model", "capacity", "status", "owner", "notes"]


class DriverForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Driver
        fields = [
            "name",
            "phone",
            "license_number",
            "license_expiry",
            "documents_note",
            "status",
        ]
        widgets = {
            "license_expiry": forms.DateInput(attrs={"type": "date"}),
        }


class RouteForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Route
        fields = ["name", "description", "vehicle", "assigned_driver"]


class StopForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = Stop
        fields = ["route", "name", "sequence", "pickup_time", "dropoff_time"]
        widgets = {
            "pickup_time": forms.TimeInput(attrs={"type": "time"}),
            "dropoff_time": forms.TimeInput(attrs={"type": "time"}),
        }


class TransportAssignmentForm(BaseFormMixin, forms.ModelForm):
    class Meta:
        model = TransportAssignment
        fields = [
            "route",
            "stop",
            "direction",
            "transport_fee_per_term",
            "is_active",
            "active_from",
        ]
        widgets = {
            "active_from": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        route_id = None
        if "data" in kwargs and kwargs["data"]:
            route_id = kwargs["data"].get("route")
        super().__init__(*args, **kwargs)
        stops = Stop.objects.all()
        if route_id:
            stops = stops.filter(route_id=route_id)
        self.fields["stop"].queryset = stops.order_by("sequence")