from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.AnnouncementListView.as_view(), name="announcements"),
    path(
        "announcements/",
        views.AnnouncementListView.as_view(),
        name="announcement_list",
    ),
    path(
        "announcements/add/",
        views.AnnouncementCreateView.as_view(),
        name="announcement_add",
    ),
    path(
        "announcements/<int:pk>/",
        views.AnnouncementDetailView.as_view(),
        name="announcement_detail",
    ),
    path(
        "announcements/<int:pk>/edit/",
        views.AnnouncementUpdateView.as_view(),
        name="announcement_edit",
    ),
    path(
        "announcements/<int:pk>/delete/",
        views.AnnouncementDeleteView.as_view(),
        name="announcement_delete",
    ),
    path("my/", views.NotificationListView.as_view(), name="list"),
    path(
        "my/<int:pk>/read/",
        views.NotificationMarkReadView.as_view(),
        name="mark_read",
    ),
    path("inbox/", views.InboxListView.as_view(), name="inbox"),
    path("inbox/<int:pk>/", views.InboxDetailView.as_view(), name="inbox_detail"),
    path("inbox/compose/", views.InboxComposeView.as_view(), name="compose"),
    path("sent/", views.SentListView.as_view(), name="sent"),
]