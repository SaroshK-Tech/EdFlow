from django.contrib import admin

from .models import BackupJob, BackupProfile


@admin.register(BackupProfile)
class BackupProfileAdmin(admin.ModelAdmin):
    list_display = ["name", "destination_path", "keep_count", "is_active", "updated_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "destination_path"]


@admin.register(BackupJob)
class BackupJobAdmin(admin.ModelAdmin):
    list_display = [
        "archive_name", "profile", "kind", "status", "archive_size",
        "verified", "started_at", "finished_at",
    ]
    list_filter = ["status", "kind", "verified"]
    search_fields = ["archive_name", "profile__name", "note", "error"]
    readonly_fields = [
        "archive_name", "archive_path", "archive_size", "checksum",
        "database_file", "entries", "verified", "verified_at", "started_at",
        "finished_at", "created_by",
    ]