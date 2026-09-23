from django.conf import settings
from django.db import models
from django.utils import timezone


class Category(models.Model):
    """Inventory item category (spec §22 'Categories')."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Supplier(models.Model):
    """Vendor from whom stock is purchased (spec §22 'Suppliers')."""

    name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class InventoryItem(models.Model):
    """A stockable item tracked by the store (spec §22)."""

    name = models.CharField(max_length=150)
    sku = models.CharField(max_length=50, blank=True, unique=True)
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="items",
    )
    unit = models.CharField(
        max_length=20,
        blank=True,
        default="pcs",
        help_text="Unit of measure, e.g. pcs, reams, boxes, litres.",
    )
    min_stock = models.PositiveIntegerField(
        default=0, help_text="Reorder level; drops to 'Low stock' below this."
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Inventory Item"
        verbose_name_plural = "Inventory Items"

    def __str__(self):
        return self.name

    def _stock_base(self):
        from django.db.models import Sum

        purchases = (
            self.purchases.aggregate(total=Sum("quantity"))["total"] or 0
        )
        issues = self.issues.aggregate(total=Sum("quantity"))["total"] or 0
        returns = self.returns.aggregate(total=Sum("quantity"))["total"] or 0
        adjustments = self.adjustments.aggregate(total=Sum("quantity"))["total"] or 0
        return purchases - issues + returns + adjustments

    @property
    def current_stock(self):
        return self._stock_base()

    @property
    def is_low_stock(self):
        return self.current_stock <= self.min_stock

    @property
    def stock_value(self):
        last = self.purchases.order_by("-purchase_date", "-id").first()
        cost = last.unit_cost if last else 0
        return cost * self.current_stock


class Purchase(models.Model):
    """Stock-in record (spec §22 'Purchases')."""

    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="purchases"
    )
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    supplier = models.ForeignKey(
        Supplier, null=True, blank=True, on_delete=models.SET_NULL, related_name="purchases"
    )
    purchase_date = models.DateField(default=timezone.localdate)
    invoice_number = models.CharField(max_length=50, blank=True)
    notes = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-purchase_date", "-id"]

    def __str__(self):
        return f"{self.item} +{self.quantity} ({self.purchase_date})"

    @property
    def total_cost(self):
        return self.quantity * self.unit_cost


class ItemIssue(models.Model):
    """Stock-out / issue to a staff member or department (spec §22 'Issues')."""

    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="issues"
    )
    quantity = models.PositiveIntegerField()
    issued_to = models.ForeignKey(
        "staff.Staff",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inventory_issues",
    )
    department = models.CharField(max_length=100, blank=True)
    issue_date = models.DateField(default=timezone.localdate)
    purpose = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-issue_date", "-id"]
        verbose_name_plural = "Issues"

    def __str__(self):
        return f"{self.item} -{self.quantity} ({self.issue_date})"


class ItemReturn(models.Model):
    """Return of an issued item to stock (spec §22 'Returns')."""

    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="returns"
    )
    quantity = models.PositiveIntegerField()
    returned_by = models.ForeignKey(
        "staff.Staff",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="inventory_returns",
    )
    return_date = models.DateField(default=timezone.localdate)
    condition = models.CharField(max_length=100, blank=True)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-return_date", "-id"]
        verbose_name_plural = "Returns"

    def __str__(self):
        return f"{self.item} +{self.quantity} (return {self.return_date})"


class StockAdjustment(models.Model):
    """Manual stock correction (positive adds, negative removes)"""

    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="adjustments"
    )
    quantity = models.IntegerField(
        help_text="Positive adds to stock, negative removes from stock."
    )
    reason = models.CharField(max_length=200)
    date = models.DateField(default=timezone.localdate)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.item} adj {self.quantity:+d} ({self.date})"


class AssetLocation(models.Model):
    """Where assets are kept (spec §22 'Asset locations')."""

    name = models.CharField(max_length=100)
    building = models.CharField(max_length=100, blank=True)
    room = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AssetStatus(models.TextChoices):
    IN_SERVICE = "in_service", "In Service"
    MAINTENANCE = "maintenance", "Under Maintenance"
    DISPOSED = "disposed", "Disposed"


class Asset(models.Model):
    """A fixed / trackable asset such as furniture or electronics (spec §22)."""

    name = models.CharField(max_length=150)
    asset_code = models.CharField(max_length=50, blank=True, unique=True)
    category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="assets"
    )
    serial_number = models.CharField(max_length=100, blank=True)
    supplier = models.ForeignKey(
        Supplier, null=True, blank=True, on_delete=models.SET_NULL, related_name="assets"
    )
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    warranty_until = models.DateField(null=True, blank=True)
    location = models.ForeignKey(
        AssetLocation, null=True, blank=True, on_delete=models.SET_NULL, related_name="assets"
    )
    status = models.CharField(
        max_length=20, choices=AssetStatus.choices, default=AssetStatus.IN_SERVICE
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.asset_code and f"{self.asset_code} — {self.name}" or self.name

    @property
    def current_assignee(self):
        active = self.assignments.filter(returned_on__isnull=True).order_by("-assigned_on").first()
        return active.assigned_to if active else None

    @property
    def maintenance_total(self):
        from django.db.models import Sum

        return self.maintenances.aggregate(total=Sum("cost"))["total"] or 0


class AssetAssignment(models.Model):
    """Temporary or permanent assignment of an asset to a staff member (spec §22)."""

    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="assignments"
    )
    assigned_to = models.ForeignKey(
        "staff.Staff", on_delete=models.CASCADE, related_name="asset_assignments"
    )
    assigned_on = models.DateField(default=timezone.localdate)
    returned_on = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-assigned_on"]

    def __str__(self):
        return f"{self.asset} → {self.assigned_to}"


class AssetMaintenance(models.Model):
    """Maintenance record for an asset (spec §22 'Maintenance')."""

    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="maintenances"
    )
    date = models.DateField(default=timezone.localdate)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    description = models.CharField(max_length=250)
    performed_by = models.CharField(max_length=100, blank=True)
    completed = models.BooleanField(default=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.asset} — {self.date}"


class AssetDisposal(models.Model):
    """Disposal record for an asset (spec §22 'Disposal')."""

    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name="disposals"
    )
    date = models.DateField(default=timezone.localdate)
    reason = models.CharField(max_length=200)
    method = models.CharField(
        max_length=50, blank=True, help_text="e.g. auction, scrapped, donated."
    )
    proceeds = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name_plural = "Disposals"

    def __str__(self):
        return f"{self.asset} — {self.date}"