from django.contrib import admin

from .models import Expense, ExpenseCategory, Refund


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "expense_count")
    search_fields = ("name",)

    def expense_count(self, obj):
        return obj.expenses.count()

    expense_count.short_description = "Expenses"


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "amount", "method", "expense_date", "payee")
    list_filter = ("category", "method", "expense_date")
    search_fields = ("title", "payee", "invoice_number")


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("student", "amount", "method", "refund_date", "reason")
    list_filter = ("method", "refund_date")
    search_fields = ("student__first_name", "student__last_name", "reason")