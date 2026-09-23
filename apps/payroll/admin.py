from django.contrib import admin

from .models import PayrollRun, PaySlip, SalaryComponent


@admin.register(SalaryComponent)
class SalaryComponentAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "amount", "percentage", "applies_to", "is_taxable", "active")
    list_filter = ("kind", "applies_to", "active")
    search_fields = ("name",)


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = ("title", "month", "year", "status", "created_by", "created_at", "paid_on")
    list_filter = ("status", "year", "month")
    search_fields = ("title",)


@admin.register(PaySlip)
class PaySlipAdmin(admin.ModelAdmin):
    list_display = ("run", "staff", "basic", "allowances_total", "deductions_total", "net")
    list_filter = ("run__status",)
    search_fields = ("staff__first_name", "staff__employee_code")