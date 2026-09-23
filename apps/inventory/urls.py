from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.ItemListView.as_view(), name="list"),
    path("items/add/", views.ItemCreateView.as_view(), name="item_add"),
    path("items/<int:pk>/", views.ItemDetailView.as_view(), name="item_detail"),
    path("items/<int:pk>/edit/", views.ItemUpdateView.as_view(), name="item_edit"),
    path("items/<int:pk>/delete/", views.ItemDeleteView.as_view(), name="item_delete"),
    path("categories/", views.CategoryListView.as_view(), name="category_list"),
    path("categories/add/", views.CategoryCreateView.as_view(), name="category_add"),
    path(
        "categories/<int:pk>/edit/",
        views.CategoryUpdateView.as_view(),
        name="category_edit",
    ),
    path(
        "categories/<int:pk>/delete/",
        views.CategoryDeleteView.as_view(),
        name="category_delete",
    ),
    path("suppliers/", views.SupplierListView.as_view(), name="supplier_list"),
    path("suppliers/add/", views.SupplierCreateView.as_view(), name="supplier_add"),
    path(
        "suppliers/<int:pk>/edit/",
        views.SupplierUpdateView.as_view(),
        name="supplier_edit",
    ),
    path(
        "suppliers/<int:pk>/delete/",
        views.SupplierDeleteView.as_view(),
        name="supplier_delete",
    ),
    path("purchases/", views.PurchaseListView.as_view(), name="purchase_list"),
    path("purchases/add/", views.PurchaseCreateView.as_view(), name="purchase_add"),
    path(
        "purchases/<int:pk>/delete/",
        views.PurchaseDeleteView.as_view(),
        name="purchase_delete",
    ),
    path("issues/", views.IssueListView.as_view(), name="issue_list"),
    path("issues/add/", views.IssueCreateView.as_view(), name="issue_add"),
    path("returns/", views.ReturnListView.as_view(), name="return_list"),
    path("returns/add/", views.ReturnCreateView.as_view(), name="return_add"),
    path(
        "adjustments/add/",
        views.AdjustmentCreateView.as_view(),
        name="adjustment_add",
    ),
    path("assets/", views.AssetListView.as_view(), name="asset_list"),
    path("assets/<int:pk>/", views.AssetDetailView.as_view(), name="asset_detail"),
    path("assets/add/", views.AssetCreateView.as_view(), name="asset_add"),
    path("assets/<int:pk>/edit/", views.AssetUpdateView.as_view(), name="asset_edit"),
    path(
        "assets/<int:pk>/delete/",
        views.AssetDeleteView.as_view(),
        name="asset_delete",
    ),
    path("locations/", views.AssetLocationListView.as_view(), name="location_list"),
    path("locations/add/", views.AssetLocationCreateView.as_view(), name="location_add"),
    path("assignments/", views.AssetAssignmentListView.as_view(), name="assignment_list"),
    path("assignments/add/", views.AssetAssignmentCreateView.as_view(), name="assignment_add"),
    path("maintenance/", views.MaintenanceListView.as_view(), name="maintenance_list"),
    path("maintenance/add/", views.MaintenanceCreateView.as_view(), name="maintenance_add"),
    path("disposals/", views.DisposalListView.as_view(), name="disposal_list"),
    path("disposals/add/", views.DisposalCreateView.as_view(), name="disposal_add"),
    path("reports/", views.ReportView.as_view(), name="reports"),
]