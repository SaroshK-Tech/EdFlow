from django.contrib import admin

from .models import (
    Author,
    Book,
    BookCopy,
    Category,
    Fine,
    Issue,
    LibrarySettings,
    Member,
    Publisher,
)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "category", "isbn", "available_copies", "total_copies")
    list_filter = ("category", "language")
    search_fields = ("title", "isbn", "author__name")


@admin.register(BookCopy)
class BookCopyAdmin(admin.ModelAdmin):
    list_display = ("barcode", "book", "status", "condition", "acquired_on")
    list_filter = ("status", "condition")
    search_fields = ("barcode", "book__title")


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("name", "student", "staff", "phone", "joined_on", "status")
    list_filter = ("status",)
    search_fields = ("name", "student__admission_number", "staff__employee_code", "phone")


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ("copy", "member", "issued_on", "due_date", "returned_on", "fine_amount", "fine_paid")
    list_filter = ("returned_on", "fine_paid")
    search_fields = ("copy__barcode", "member__name")


@admin.register(Fine)
class FineAdmin(admin.ModelAdmin):
    list_display = ("issue", "amount", "reason", "paid", "created_at")
    list_filter = ("paid",)
    search_fields = ("issue__member__name", "issue__copy__barcode", "reason")


@admin.register(LibrarySettings)
class LibrarySettingsAdmin(admin.ModelAdmin):
    list_display = ("fine_per_day", "loan_duration_days", "lost_book_fine")