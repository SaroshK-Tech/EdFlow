from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("", views.DocumentDashboardView.as_view(), name="list"),
    path("templates/", views.TemplateListView.as_view(), name="templates"),
    path("templates/add/", views.TemplateCreateView.as_view(), name="template_add"),
    path("templates/<int:pk>/edit/", views.TemplateUpdateView.as_view(), name="template_edit"),
    path("templates/<int:pk>/delete/", views.TemplateDeleteView.as_view(), name="template_delete"),
    path("generate/<str:doc_type>/", views.GenerateDocumentView.as_view(), name="generate"),
    path("history/", views.GeneratedListView.as_view(), name="history"),
    path("history/<int:pk>/delete/", views.DocumentDeleteView.as_view(), name="delete"),
]