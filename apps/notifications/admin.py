from django.contrib import admin

from .models import Announcement, InboxMessage, Notification


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "audience", "is_emergency", "is_pinned", "is_active", "created_by", "created_at")
    list_filter = ("audience", "is_emergency", "is_pinned", "is_active")
    search_fields = ("title", "body", "message")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "text", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("text", "recipient__username")


@admin.register(InboxMessage)
class InboxMessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "recipient", "subject", "is_important", "sent_at", "read_at")
    list_filter = ("is_important",)
    search_fields = ("subject", "body", "sender__username", "recipient__username")