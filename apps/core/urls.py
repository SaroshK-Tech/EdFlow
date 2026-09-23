from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("search/", views.global_search, name="search"),
    path("module/<slug:module>/", views.module_placeholder, name="module"),
]