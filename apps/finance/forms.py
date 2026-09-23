from django import forms

from .models import Expense, ExpenseCategory, Refund


def _decorate(form):
    for field in form.fields.values():
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs.setdefault("class", "form-check-input")
        elif isinstance(field.widget, forms.Select):
            field.widget.attrs.setdefault("class", "form-select")
        else:
            field.widget.attrs.setdefault("class", "form-control")


class DateInput(forms.DateInput):
    input_type = "date"


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ["name", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            "title",
            "amount",
            "category",
            "expense_date",
            "method",
            "payee",
            "invoice_number",
            "notes",
        ]
        widgets = {"expense_date": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)


class RefundForm(forms.ModelForm):
    class Meta:
        model = Refund
        fields = ["student", "amount", "refund_date", "method", "reason", "reference", "notes"]
        widgets = {"refund_date": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)