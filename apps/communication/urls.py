from django.urls import path

from . import views

app_name = "communication"

urlpatterns = [
    path("", views.CommunicationDashboardView.as_view(), name="list"),
    path("compose/", views.ComposeMessageView.as_view(), name="compose"),
    path("batches/", views.BatchListView.as_view(), name="batch_list"),
    path("batches/<int:pk>/", views.BatchDetailView.as_view(), name="batch_detail"),
    path("messages/<int:pk>/", views.OutboxDetailView.as_view(), name="message_detail"),
    path("messages/<int:pk>/cancel/", views.OutboxCancelView.as_view(), name="message_cancel"),
    path("messages/<int:pk>/retry/", views.OutboxRetryView.as_view(), name="message_retry"),
    path("templates/", views.TemplateListView.as_view(), name="templates"),
    path("templates/add/", views.TemplateCreateView.as_view(), name="template_add"),
    path("templates/<int:pk>/edit/", views.TemplateUpdateView.as_view(), name="template_edit"),
    path("templates/<int:pk>/delete/", views.TemplateDeleteView.as_view(), name="template_delete"),
    # Local Android gateway API
    path("gateway/claim/", views.gateway_claim, name="gateway_claim"),
    path("gateway/report/", views.gateway_report, name="gateway_report"),
    path("gateway/health/", views.gateway_health, name="gateway_health"),
]