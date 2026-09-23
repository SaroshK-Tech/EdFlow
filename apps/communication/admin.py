from django.contrib import admin

from .models import MessageBatch, MessageTemplate, Outbox


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "channel", "is_active", "is_system")
    list_filter = ("channel", "is_active", "is_system")
    search_fields = ("name", "key", "body")


@admin.register(MessageBatch)
class MessageBatchAdmin(admin.ModelAdmin):
    list_display = ("subject", "channel", "recipient_count", "created_by", "created_at")
    list_filter = ("channel",)
    search_fields = ("subject",)

    def recipient_count(self, obj):
        return obj.recipient_count

    recipient_count.short_description = "Messages"


class OutboxAdmin(admin.ModelAdmin):
    list_display = (
        "recipient",
        "channel",
        "subject",
        "status",
        "priority",
        "attempt_count",
        "created_at",
        "sent_at",
    )
    list_filter = ("status", "channel", "priority")
    search_fields = ("recipient", "message", "template_key")

    def subject(self, obj):
        return obj.template_key or (obj.batch.subject if obj.batch else "—")

    subject.short_description = "Template/Batch"


admin.site.register(Outbox, OutboxAdmin)