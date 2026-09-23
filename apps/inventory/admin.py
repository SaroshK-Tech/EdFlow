from django.contrib import admin

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


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "item_count")
    search_fields = ("name",)

    def item_count(self, obj):
        return obj.items.count()

    item_count.short_description = "Items"


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "phone", "email")
    search_fields = ("name", "contact_person", "phone", "email")


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "min_stock", "current_stock", "is_low_stock")
    list_filter = ("category",)
    search_fields = ("name", "sku")

    def current_stock(self, obj):
        return obj.current_stock

    def is_low_stock(self, obj):
        return obj.is_low_stock

    is_low_stock.boolean = True


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("item", "quantity", "unit_cost", "supplier", "purchase_date")
    list_filter = ("supplier", "purchase_date")
    search_fields = ("item__name", "invoice_number")


@admin.register(ItemIssue)
class ItemIssueAdmin(admin.ModelAdmin):
    list_display = ("item", "quantity", "issued_to", "issue_date")
    list_filter = ("issue_date",)
    search_fields = ("item__name",)


@admin.register(ItemReturn)
class ItemReturnAdmin(admin.ModelAdmin):
    list_display = ("item", "quantity", "returned_by", "return_date")
    list_filter = ("return_date",)


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("item", "quantity", "reason", "date")
    list_filter = ("date",)


@admin.register(AssetLocation)
class AssetLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "building", "room")


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("name", "asset_code", "category", "location", "status", "purchase_cost")
    list_filter = ("status", "category", "location")
    search_fields = ("name", "asset_code", "serial_number")


@admin.register(AssetAssignment)
class AssetAssignmentAdmin(admin.ModelAdmin):
    list_display = ("asset", "assigned_to", "assigned_on", "returned_on")
    list_filter = ("assigned_on",)


@admin.register(AssetMaintenance)
class AssetMaintenanceAdmin(admin.ModelAdmin):
    list_display = ("asset", "date", "cost", "completed")
    list_filter = ("date", "completed")


@admin.register(AssetDisposal)
class AssetDisposalAdmin(admin.ModelAdmin):
    list_display = ("asset", "date", "reason", "method", "proceeds")
    list_filter = ("date",)