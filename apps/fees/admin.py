from django.contrib import admin

from .models import FeeHead, FeePayment


@admin.register(FeeHead)
class FeeHeadAdmin(admin.ModelAdmin):
    list_display = ("name", "amount", "is_recurring", "is_active")
    list_filter = ("is_recurring", "is_active")
    search_fields = ("name",)


@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = (
        "receipt_number",
        "student",
        "fee_head",
        "amount",
        "method",
        "paid_on",
        "received_by",
    )
    list_filter = ("method", "paid_on")
    search_fields = ("receipt_number", "student__admission_number", "student__first_name")
    date_hierarchy = "paid_on"