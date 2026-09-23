from django.urls import path

from . import views

app_name = "fees"

urlpatterns = [
    path("", views.FeeHeadListView.as_view(), name="heads"),
    path("heads/add/", views.FeeHeadCreateView.as_view(), name="head_add"),
    path("heads/<int:pk>/edit/", views.FeeHeadUpdateView.as_view(), name="head_edit"),
    path("payments/", views.PaymentListView.as_view(), name="payments"),
    path("payments/add/", views.PaymentCreateView.as_view(), name="payment_add"),
    path("vouchers/", views.VoucherListView.as_view(), name="vouchers"),
    path("vouchers/generate/", views.VoucherGenerateView.as_view(), name="voucher_generate"),
    path("vouchers/print/", views.VoucherPrintView.as_view(), name="voucher_print"),
    path("vouchers/<int:pk>/", views.VoucherDetailView.as_view(), name="voucher_detail"),
    path("vouchers/<int:pk>/delete/", views.VoucherDeleteView.as_view(), name="voucher_delete"),
    path("concessions/", views.ConcessionListView.as_view(), name="concessions"),
    path("concessions/add/", views.ConcessionCreateView.as_view(), name="concession_add"),
    path("concessions/<int:pk>/edit/", views.ConcessionUpdateView.as_view(), name="concession_edit"),
    path(
        "concessions/<int:pk>/delete/",
        views.ConcessionDeleteView.as_view(),
        name="concession_delete",
    ),
    path(
        "concession-assignments/",
        views.StudentConcessionListView.as_view(),
        name="concession_assignments",
    ),
    path(
        "concession-assignments/add/",
        views.StudentConcessionCreateView.as_view(),
        name="concession_assign",
    ),
    path(
        "concession-assignments/<int:pk>/delete/",
        views.StudentConcessionDeleteView.as_view(),
        name="concession_unassign",
    ),
]