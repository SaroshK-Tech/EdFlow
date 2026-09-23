from django import forms

from .models import House, HouseActivity, HousePoint, HouseResult


class HouseForm(forms.ModelForm):
    class Meta:
        model = House
        fields = [
            "name",
            "color",
            "motto",
            "captain",
            "vice_captain",
            "staff_coordinator",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class HousePointForm(forms.ModelForm):
    class Meta:
        model = HousePoint
        fields = ["house", "student", "date", "points", "reason"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class HouseActivityForm(forms.ModelForm):
    class Meta:
        model = HouseActivity
        fields = ["house", "name", "date", "kind", "description"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class HouseResultForm(forms.ModelForm):
    class Meta:
        model = HouseResult
        fields = ["activity", "house", "rank", "points_awarded"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")