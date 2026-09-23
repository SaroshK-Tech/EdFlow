from django.urls import path

from . import views

app_name = "staff"

urlpatterns = [
    path("", views.StaffListView.as_view(), name="list"),
    path("add/", views.StaffCreateView.as_view(), name="add"),
    path("<int:pk>/", views.StaffDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.StaffUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.StaffDeleteView.as_view(), name="delete"),
    path("<int:pk>/documents/add/", views.StaffDocumentCreateView.as_view(), name="document_add"),
    path("documents/<int:pk>/delete/", views.StaffDocumentDeleteView.as_view(), name="document_delete"),
    path("<int:pk>/id-card/", views.StaffIdCardView.as_view(), name="id_card"),
]