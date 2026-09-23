from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("", views.FinanceDashboardView.as_view(), name="list"),
    path("expenses/", views.ExpenseListView.as_view(), name="expense_list"),
    path("expenses/export/", views.ExpenseExportView.as_view(), name="expense_export"),
    path("expenses/add/", views.ExpenseCreateView.as_view(), name="expense_add"),
    path(
        "expenses/<int:pk>/edit/",
        views.ExpenseUpdateView.as_view(),
        name="expense_edit",
    ),
    path(
        "expenses/<int:pk>/delete/",
        views.ExpenseDeleteView.as_view(),
        name="expense_delete",
    ),
    path(
        "expense-categories/",
        views.ExpenseCategoryListView.as_view(),
        name="category_list",
    ),
    path(
        "expense-categories/add/",
        views.ExpenseCategoryCreateView.as_view(),
        name="category_add",
    ),
    path(
        "expense-categories/<int:pk>/edit/",
        views.ExpenseCategoryUpdateView.as_view(),
        name="category_edit",
    ),
    path(
        "expense-categories/<int:pk>/delete/",
        views.ExpenseCategoryDeleteView.as_view(),
        name="category_delete",
    ),
    path("refunds/", views.RefundListView.as_view(), name="refund_list"),
    path("refunds/export/", views.RefundExportView.as_view(), name="refund_export"),
    path("refunds/add/", views.RefundCreateView.as_view(), name="refund_add"),
    path("reports/", views.ReportsView.as_view(), name="reports"),
    path("reports/cashflow/export/", views.CashflowExportView.as_view(), name="cashflow_export"),
]