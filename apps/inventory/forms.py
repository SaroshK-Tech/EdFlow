from django import forms

from .models import (
    Asset,
    AssetAssignment,
    AssetDisposal,
    AssetLocation,
    AssetMaintenance,
    Category,
    InventoryItem,
    ItemIssue,
    ItemReturn,
    Purchase,
    StockAdjustment,
    Supplier,
)


def _decorate(form):
    for field in form.fields.values():
        if isinstance(field.widget, forms.CheckboxInput) or isinstance(
            field.widget, forms.CheckboxSelectMultiple
        ):
            field.widget.attrs.setdefault("class", "form-check-input")
        elif isinstance(field.widget, forms.Select):
            field.widget.attrs.setdefault("class", "form-select")
        else:
            field.widget.attrs.setdefault("class", "form-control")


class DateInput(forms.DateInput):
    input_type = "date"


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "contact_person", "phone", "email", "address"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ["name", "sku", "category", "unit", "min_stock", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = [
            "item",
            "quantity",
            "unit_cost",
            "supplier",
            "purchase_date",
            "invoice_number",
            "notes",
        ]
        widgets = {"purchase_date": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)


class ItemIssueForm(forms.ModelForm):
    class Meta:
        model = ItemIssue
        fields = ["item", "quantity", "issued_to", "department", "issue_date", "purpose"]
        widgets = {"issue_date": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)

    def clean_quantity(self):
        qty = self.cleaned_data["quantity"]
        item = self.cleaned_data["item"]
        if qty > item.current_stock:
            raise forms.ValidationError(
                f"Only {item.current_stock} unit(s) of '{item}' are in stock."
            )
        return qty


class ItemReturnForm(forms.ModelForm):
    class Meta:
        model = ItemReturn
        fields = ["item", "quantity", "returned_by", "return_date", "condition", "notes"]
        widgets = {"return_date": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)


class StockAdjustmentForm(forms.ModelForm):
    class Meta:
        model = StockAdjustment
        fields = ["item", "quantity", "reason", "date"]
        widgets = {"date": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = [
            "name",
            "asset_code",
            "category",
            "serial_number",
            "supplier",
            "purchase_date",
            "purchase_cost",
            "warranty_until",
            "location",
            "status",
            "notes",
        ]
        widgets = {"purchase_date": DateInput(), "warranty_until": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)


class AssetLocationForm(forms.ModelForm):
    class Meta:
        model = AssetLocation
        fields = ["name", "building", "room", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)


class AssetAssignmentForm(forms.ModelForm):
    class Meta:
        model = AssetAssignment
        fields = ["asset", "assigned_to", "assigned_on", "returned_on", "notes"]
        widgets = {"assigned_on": DateInput(), "returned_on": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)


class AssetMaintenanceForm(forms.ModelForm):
    class Meta:
        model = AssetMaintenance
        fields = ["asset", "date", "cost", "description", "performed_by", "completed"]
        widgets = {"date": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)


class AssetDisposalForm(forms.ModelForm):
    class Meta:
        model = AssetDisposal
        fields = ["asset", "date", "reason", "method", "proceeds"]
        widgets = {"date": DateInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _decorate(self)