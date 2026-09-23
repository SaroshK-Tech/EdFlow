from django.urls import path

from . import views

app_name = "parents"

urlpatterns = [
    path("", views.ParentListView.as_view(), name="list"),
    path("add/", views.ParentCreateView.as_view(), name="add"),
    path("<int:pk>/", views.ParentDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.ParentUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.ParentDeleteView.as_view(), name="delete"),
]