from django.contrib import messages
from django.db.models import (
    Count,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
)
from django.db.models.functions import Coalesce
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin

from .forms import (
    AssetAssignmentForm,
    AssetDisposalForm,
    AssetForm,
    AssetLocationForm,
    AssetMaintenanceForm,
    CategoryForm,
    InventoryItemForm,
    ItemIssueForm,
    ItemReturnForm,
    PurchaseForm,
    StockAdjustmentForm,
    SupplierForm,
)
from .models import (
    Asset,
    AssetAssignment,
    AssetDisposal,
    AssetLocation,
    AssetMaintenance,
    AssetStatus,
    Category,
    InventoryItem,
    ItemIssue,
    ItemReturn,
    Purchase,
    StockAdjustment,
    Supplier,
)


def _sub_sum(model, field, output_field=IntegerField()):
    return Coalesce(
        Subquery(
            model.objects.filter(item=OuterRef("pk"))
            .values("item")
            .annotate(total=Sum(field))
            .values("total")
        ),
        0,
        output_field=output_field,
    )


def item_annotations():
    return {
        "qty_purchased": _sub_sum(Purchase, "quantity"),
        "qty_issued": _sub_sum(ItemIssue, "quantity"),
        "qty_returned": _sub_sum(ItemReturn, "quantity"),
        "qty_adjusted": _sub_sum(StockAdjustment, "quantity"),
    }


def available_expression():
    return (
        F("qty_purchased") - F("qty_issued") + F("qty_returned") + F("qty_adjusted")
    )


# ---------- Categories ----------


class CategoryListView(EdFlowMixin, SearchMixin, ListView):
    model = Category
    template_name = "inventory/category_list.html"
    context_object_name = "categories"
    page_title = "Categories"
    page_subtitle = "Inventory item categories"
    active_page = "inventory"
    search_fields = ["name", "description"]

    def get_queryset(self):
        return (
            super().get_queryset().annotate(item_count=Count("items", distinct=True))
        )


class CategoryCreateView(EdFlowMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "inventory/category_form.html"
    page_title = "Add Category"
    active_page = "inventory"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"inventory.category_create {self.object.name}",
              object_type="Category", object_id=self.object.pk)
        messages.success(self.request, f"Category {self.object.name} created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:category_list")


class CategoryUpdateView(EdFlowMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "inventory/category_form.html"
    page_title = "Edit Category"
    active_page = "inventory"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Category updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:category_list")


class CategoryDeleteView(EdFlowMixin, DeleteView):
    model = Category
    template_name = "inventory/confirm_delete.html"
    object_context_name = "object"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object_label"] = "category"
        ctx["cancel_url"] = reverse("inventory:category_list")
        ctx["page_title"] = "Delete Category"
        ctx["active_page"] = "inventory"
        try:
            count = self.object.items.count()
        except ValueError:
            count = 0
        ctx["warning"] = f" has {count} item(s) linked to it." if count else ""
        return ctx

    def form_valid(self, form):
        audit(self.request, f"inventory.category_delete {self.object.name}")
        messages.success(self.request, "Category deleted.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("inventory:category_list")


# ---------- Suppliers ----------


class SupplierListView(EdFlowMixin, SearchMixin, ListView):
    model = Supplier
    template_name = "inventory/supplier_list.html"
    context_object_name = "suppliers"
    page_title = "Suppliers"
    page_subtitle = "Vendors purchasing stock from"
    active_page = "inventory"
    search_fields = ["name", "contact_person", "phone", "email"]


class SupplierCreateView(EdFlowMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = "inventory/supplier_form.html"
    page_title = "Add Supplier"
    active_page = "inventory"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"inventory.supplier_create {self.object.name}",
              object_type="Supplier", object_id=self.object.pk)
        messages.success(self.request, f"Supplier {self.object.name} created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:supplier_list")


class SupplierUpdateView(EdFlowMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = "inventory/supplier_form.html"
    page_title = "Edit Supplier"
    active_page = "inventory"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Supplier updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:supplier_list")


class SupplierDeleteView(EdFlowMixin, DeleteView):
    model = Supplier
    template_name = "inventory/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object_label"] = "supplier"
        ctx["cancel_url"] = reverse("inventory:supplier_list")
        ctx["page_title"] = "Delete Supplier"
        ctx["active_page"] = "inventory"
        ctx["warning"] = self.object.purchases.count() and f" has {self.object.purchases.count()} purchase record(s)."
        return ctx

    def form_valid(self, form):
        audit(self.request, f"inventory.supplier_delete {self.object.name}")
        messages.success(self.request, "Supplier deleted.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("inventory:supplier_list")


# ---------- Items ----------


class ItemListView(EdFlowMixin, SearchMixin, ListView):
    model = InventoryItem
    template_name = "inventory/item_list.html"
    context_object_name = "items"
    paginate_by = 25
    page_title = "Inventory Items"
    page_subtitle = "Stock levels, purchases, issues and returns"
    active_page = "inventory"
    search_fields = ["name", "sku", "category__name"]
    search_placeholder = "Search items…"

    def get_queryset(self):
        qs = super().get_queryset().select_related("category").annotate(
            **item_annotations()
        )
        low = self.request.GET.get("low")
        qs = qs.annotate(available=available_expression())
        if low == "1":
            qs = qs.filter(available__lte=F("min_stock"))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_low"] = self.request.GET.get("low") == "1"
        total_qs = (
            InventoryItem.objects.select_related("category")
            .annotate(**item_annotations())
        )
        ctx["items_total"] = total_qs.count()
        ctx["low_stock_count"] = (
            total_qs.annotate(avail=available_expression()).filter(avail__lte=F("min_stock")).count()
        )
        return ctx


class ItemDetailView(EdFlowMixin, DetailView):
    model = InventoryItem
    template_name = "inventory/item_detail.html"
    context_object_name = "item"
    page_title = "Item Details"
    active_page = "inventory"

    def get_queryset(self):
        return super().get_queryset().select_related("category").annotate(
            **item_annotations()
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        item = ctx["item"]
        item.available = (
            item.qty_purchased - item.qty_issued + item.qty_returned + item.qty_adjusted
        )
        ctx["purchases"] = self.object.purchases.select_related("supplier").order_by("-purchase_date")[:10]
        ctx["issues"] = self.object.issues.select_related("issued_to").order_by("-issue_date")[:10]
        ctx["returns"] = self.object.returns.select_related("returned_by").order_by("-return_date")[:10]
        ctx["adjustments"] = self.object.adjustments.order_by("-date")[:10]
        return ctx


class ItemCreateView(EdFlowMixin, CreateView):
    model = InventoryItem
    form_class = InventoryItemForm
    template_name = "inventory/item_form.html"
    page_title = "Add Item"
    active_page = "inventory"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"inventory.item_create {self.object.name}",
              object_type="InventoryItem", object_id=self.object.pk)
        messages.success(self.request, f"Item {self.object.name} created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:list")


class ItemUpdateView(EdFlowMixin, UpdateView):
    model = InventoryItem
    form_class = InventoryItemForm
    template_name = "inventory/item_form.html"
    page_title = "Edit Item"
    active_page = "inventory"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Item updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:list")


class ItemDeleteView(EdFlowMixin, DeleteView):
    model = InventoryItem
    template_name = "inventory/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object_label"] = "item"
        ctx["cancel_url"] = reverse("inventory:list")
        ctx["page_title"] = "Delete Item"
        ctx["active_page"] = "inventory"
        return ctx

    def form_valid(self, form):
        audit(self.request, f"inventory.item_delete {self.object.name}")
        messages.success(self.request, "Item deleted.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("inventory:list")


# ---------- Stock movements ----------


class PurchaseListView(EdFlowMixin, SearchMixin, ListView):
    model = Purchase
    template_name = "inventory/purchase_list.html"
    context_object_name = "purchases"
    paginate_by = 25
    page_title = "Purchases"
    page_subtitle = "Stock-in records"
    active_page = "inventory"
    search_fields = ["item__name", "invoice_number", "supplier__name"]

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("item", "supplier")
            .order_by("-purchase_date", "-id")
        )


class PurchaseCreateView(EdFlowMixin, CreateView):
    model = Purchase
    form_class = PurchaseForm
    template_name = "inventory/purchase_form.html"
    page_title = "Record Purchase"
    page_subtitle = "Add stock to an item"
    active_page = "inventory"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        resp = super().form_valid(form)
        audit(
            self.request,
            f"inventory.purchase {self.object.item.name} +{self.object.quantity}",
            object_type="Purchase", object_id=self.object.pk,
        )
        messages.success(
            self.request,
            f"Added {self.object.quantity} × {self.object.item.name} to stock.",
        )
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:purchase_list")


class PurchaseDeleteView(EdFlowMixin, DeleteView):
    model = Purchase
    template_name = "inventory/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object_label"] = "purchase record"
        ctx["cancel_url"] = reverse("inventory:purchase_list")
        ctx["page_title"] = "Delete Purchase"
        ctx["active_page"] = "inventory"
        return ctx

    def form_valid(self, form):
        audit(self.request, f"inventory.purchase_delete {self.object.item}")
        messages.success(self.request, "Purchase record deleted.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("inventory:purchase_list")


class IssueListView(EdFlowMixin, SearchMixin, ListView):
    model = ItemIssue
    template_name = "inventory/issue_list.html"
    context_object_name = "issues"
    paginate_by = 25
    page_title = "Issues"
    page_subtitle = "Stock issued out"
    active_page = "inventory"
    search_fields = ["item__name", "issued_to__first_name", "issued_to__last_name", "department"]

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("item", "issued_to")
            .order_by("-issue_date", "-id")
        )


class IssueCreateView(EdFlowMixin, CreateView):
    model = ItemIssue
    form_class = ItemIssueForm
    template_name = "inventory/issue_form.html"
    page_title = "Issue Item"
    page_subtitle = "Remove stock from the store"
    active_page = "inventory"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        resp = super().form_valid(form)
        audit(
            self.request,
            f"inventory.issue {self.object.item.name} -{self.object.quantity}",
            object_type="ItemIssue", object_id=self.object.pk,
        )
        messages.success(
            self.request,
            f"Issued {self.object.quantity} × {self.object.item.name}.",
        )
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:issue_list")


class ReturnListView(EdFlowMixin, SearchMixin, ListView):
    model = ItemReturn
    template_name = "inventory/return_list.html"
    context_object_name = "returns"
    paginate_by = 25
    page_title = "Returns"
    page_subtitle = "Items returned to stock"
    active_page = "inventory"
    search_fields = ["item__name", "returned_by__first_name", "returned_by__last_name"]

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("item", "returned_by")
            .order_by("-return_date", "-id")
        )


class ReturnCreateView(EdFlowMixin, CreateView):
    model = ItemReturn
    form_class = ItemReturnForm
    template_name = "inventory/return_form.html"
    page_title = "Record Return"
    page_subtitle = "Add returned stock back to the store"
    active_page = "inventory"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(
            self.request,
            f"inventory.return {self.object.item.name} +{self.object.quantity}",
            object_type="ItemReturn", object_id=self.object.pk,
        )
        messages.success(
            self.request,
            f"Returned {self.object.quantity} × {self.object.item.name} to stock.",
        )
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:return_list")


class AdjustmentCreateView(EdFlowMixin, CreateView):
    model = StockAdjustment
    form_class = StockAdjustmentForm
    template_name = "inventory/adjustment_form.html"
    page_title = "Stock Adjustment"
    page_subtitle = "Manual correction (positive adds, negative removes)"
    active_page = "inventory"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        resp = super().form_valid(form)
        audit(
            self.request,
            f"inventory.adjustment {self.object.item.name} {self.object.quantity:+d}",
            object_type="StockAdjustment", object_id=self.object.pk,
        )
        messages.success(self.request, "Stock adjustment recorded.")
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:list")


# ---------- Assets ----------


class AssetListView(EdFlowMixin, SearchMixin, ListView):
    model = Asset
    template_name = "inventory/asset_list.html"
    context_object_name = "assets"
    paginate_by = 25
    page_title = "Assets"
    page_subtitle = "Fixed assets, assignments and maintenance"
    active_page = "inventory"
    search_fields = ["name", "asset_code", "serial_number", "location__name"]

    def get_queryset(self):
        qs = super().get_queryset().select_related("category", "location").order_by("name").annotate(
            maintenance_cost=Sum("maintenances__cost")
        ).annotate(assignee_name=Subquery(
            AssetAssignment.objects.filter(
                asset=OuterRef("pk"), returned_on__isnull=True
            ).order_by("-assigned_on").values("assigned_to__first_name")[:1]
        ))
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = AssetStatus.choices
        ctx["current_status"] = self.request.GET.get("status", "")
        ctx["asset_total_value"] = (
            Asset.objects.filter(status__in=["in_service", "maintenance"])
            .aggregate(total=Sum("purchase_cost"))["total"]
            or 0
        )
        return ctx


class AssetDetailView(EdFlowMixin, DetailView):
    model = Asset
    template_name = "inventory/asset_detail.html"
    context_object_name = "asset"
    page_title = "Asset Details"
    active_page = "inventory"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        obj.assignments_qs = obj.assignments.select_related("assigned_to").order_by("-assigned_on")
        obj.maintenances_qs = obj.maintenances.order_by("-date")
        obj.disposals_qs = obj.disposals.order_by("-date")
        return obj


class AssetCreateView(EdFlowMixin, CreateView):
    model = Asset
    form_class = AssetForm
    template_name = "inventory/asset_form.html"
    page_title = "Add Asset"
    active_page = "inventory"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"inventory.asset_create {self.object.name}",
              object_type="Asset", object_id=self.object.pk)
        messages.success(self.request, f"Asset {self.object.name} created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:asset_list")


class AssetUpdateView(EdFlowMixin, UpdateView):
    model = Asset
    form_class = AssetForm
    template_name = "inventory/asset_form.html"
    page_title = "Edit Asset"
    active_page = "inventory"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Asset updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:asset_list")


class AssetDeleteView(EdFlowMixin, DeleteView):
    model = Asset
    template_name = "inventory/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object_label"] = "asset"
        ctx["cancel_url"] = reverse("inventory:asset_list")
        ctx["page_title"] = "Delete Asset"
        ctx["active_page"] = "inventory"
        return ctx

    def form_valid(self, form):
        audit(self.request, f"inventory.asset_delete {self.object.name}")
        messages.success(self.request, "Asset deleted.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("inventory:asset_list")


class AssetLocationListView(EdFlowMixin, SearchMixin, ListView):
    model = AssetLocation
    template_name = "inventory/location_list.html"
    context_object_name = "locations"
    page_title = "Asset Locations"
    active_page = "inventory"
    search_fields = ["name", "building", "room"]

    def get_queryset(self):
        return super().get_queryset().annotate(asset_count=Count("assets"))


class AssetLocationCreateView(EdFlowMixin, CreateView):
    model = AssetLocation
    form_class = AssetLocationForm
    template_name = "inventory/location_form.html"
    page_title = "Add Location"
    active_page = "inventory"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Location added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:location_list")


class AssetAssignmentListView(EdFlowMixin, SearchMixin, ListView):
    model = AssetAssignment
    template_name = "inventory/assignment_list.html"
    context_object_name = "assignments"
    paginate_by = 25
    page_title = "Asset Assignments"
    active_page = "inventory"
    search_fields = ["asset__name", "assigned_to__first_name", "assigned_to__last_name"]

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("asset", "assigned_to")
            .order_by("-assigned_on")
        )


class AssetAssignmentCreateView(EdFlowMixin, CreateView):
    model = AssetAssignment
    form_class = AssetAssignmentForm
    template_name = "inventory/assignment_form.html"
    page_title = "Assign Asset"
    active_page = "inventory"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(
            self.request,
            f"inventory.asset_assign {self.object.asset.name} to {self.object.assigned_to}",
            object_type="AssetAssignment", object_id=self.object.pk,
        )
        messages.success(self.request, "Asset assigned.")
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:assignment_list")


class MaintenanceListView(EdFlowMixin, SearchMixin, ListView):
    model = AssetMaintenance
    template_name = "inventory/maintenance_list.html"
    context_object_name = "records"
    paginate_by = 25
    page_title = "Asset Maintenance"
    active_page = "inventory"
    search_fields = ["asset__name", "description", "performed_by"]

    def get_queryset(self):
        return super().get_queryset().select_related("asset").order_by("-date", "-id")


class MaintenanceCreateView(EdFlowMixin, CreateView):
    model = AssetMaintenance
    form_class = AssetMaintenanceForm
    template_name = "inventory/maintenance_form.html"
    page_title = "Record Maintenance"
    page_subtitle = "Log a repair or service for an asset"
    active_page = "inventory"

    def form_valid(self, form):
        if form.cleaned_data["completed"]:
            asset = form.cleaned_data["asset"]
            if asset.status != "disposed":
                asset.status = "in_service"
                asset.save(update_fields=["status"])
        resp = super().form_valid(form)
        audit(
            self.request,
            f"inventory.maintenance {self.object.asset.name} cost={self.object.cost}",
            object_type="AssetMaintenance", object_id=self.object.pk,
        )
        messages.success(self.request, "Maintenance record added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:maintenance_list")


class DisposalListView(EdFlowMixin, SearchMixin, ListView):
    model = AssetDisposal
    template_name = "inventory/disposal_list.html"
    context_object_name = "disposals"
    paginate_by = 25
    page_title = "Asset Disposals"
    active_page = "inventory"
    search_fields = ["asset__name", "reason", "method"]

    def get_queryset(self):
        return super().get_queryset().select_related("asset").order_by("-date")


class DisposalCreateView(EdFlowMixin, CreateView):
    model = AssetDisposal
    form_class = AssetDisposalForm
    template_name = "inventory/disposal_form.html"
    page_title = "Dispose Asset"
    page_subtitle = "Record an asset leaving the school"
    active_page = "inventory"

    def form_valid(self, form):
        asset = form.cleaned_data["asset"]
        asset.status = "disposed"
        asset.save(update_fields=["status"])
        resp = super().form_valid(form)
        audit(
            self.request,
            f"inventory.asset_dispose {self.object.asset.name} proceeds={self.object.proceeds}",
            object_type="AssetDisposal", object_id=self.object.pk,
        )
        messages.success(self.request, "Asset disposal recorded.")
        return resp

    def get_success_url(self):
        return reverse_lazy("inventory:disposal_list")


# ---------- Reports ----------


class ReportView(EdFlowMixin, TemplateView):
    template_name = "inventory/reports.html"
    page_title = "Stock & Asset Reports"
    page_subtitle = "Valuation, low stock and asset register"
    active_page = "inventory"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base = InventoryItem.objects.select_related("category").annotate(
            **item_annotations()
        )
        base = base.annotate(avail=available_expression())
        ctx["low_items"] = list(base.filter(avail__lte=F("min_stock")).order_by("-min_stock"))
        ctx["low_count"] = len(ctx["low_items"])
        ctx["item_count"] = base.count()
        ctx["total_stock_value"] = sum(
            (it.purchases.order_by("-purchase_date", "-id").first().unit_cost if it.purchases.exists() else 0) * it.avail
            for it in base.iterator()
        )
        ctx["top_items"] = list(base.order_by("-avail")[:8])
        ctx["total_assets"] = Asset.objects.count()
        ctx["assets_value"] = (
            Asset.objects.filter(status__in=["in_service", "maintenance"])
            .aggregate(v=Sum("purchase_cost"))["v"]
            or 0
        )
        ctx["assets_by_status"] = list(
            Asset.objects.values("status").annotate(n=Count("id"))
        )
        ctx["purchase_total_year"] = (
            Purchase.objects.values("purchase_date__year")
            .annotate(total=Sum(F("quantity") * F("unit_cost")))
            .order_by("-purchase_date__year")
        )
        return ctx