from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.students.models import Student

from ...models import (
    Author,
    Book,
    BookCopy,
    Category,
    Issue,
    LibrarySettings,
    Member,
    Publisher,
)


class Command(BaseCommand):
    """Load demo library catalogue, members and an issue (spec §20)."""

    help = "Seed the library module with demo data (spec §20)."

    @transaction.atomic
    def handle(self, *args, **options):
        LibrarySettings.get_solo()

        author1, _ = Author.objects.get_or_create(name="J.K. Rowling")
        author2, _ = Author.objects.get_or_create(name="Stephen King")
        category1, _ = Category.objects.get_or_create(name="Fiction")
        category2, _ = Category.objects.get_or_create(name="Science")
        publisher, _ = Publisher.objects.get_or_create(name="Bloomsbury Publishing")

        books = [
            dict(
                isbn="9780747532699",
                title="Harry Potter and the Philosopher's Stone",
                author=author1,
                category=category1,
                publisher=publisher,
                language="English",
                edition="1st",
                shelf="A-01",
                page_count=223,
            ),
            dict(
                isbn="9780747538486",
                title="Harry Potter and the Chamber of Secrets",
                author=author1,
                category=category1,
                publisher=publisher,
                language="English",
                edition="1st",
                shelf="A-02",
                page_count=251,
            ),
            dict(
                isbn="9780307743657",
                title="The Shining",
                author=author2,
                category=category2,
                publisher=None,
                language="English",
                edition="Paperback",
                shelf="B-10",
                page_count=447,
            ),
        ]
        created_books = {}
        for spec in books:
            defaults = {
                "title": spec["title"],
                "author": spec["author"],
                "category": spec["category"],
                "language": spec["language"],
                "edition": spec["edition"],
                "shelf": spec["shelf"],
                "page_count": spec["page_count"],
                "description": f"Demo {spec['title']} import.",
            }
            if spec["publisher"]:
                defaults["publisher"] = spec["publisher"]
            book, made = Book.objects.get_or_create(isbn=spec["isbn"], defaults=defaults)
            created_books[spec["isbn"]] = book

        book1 = created_books["9780747532699"]
        book3 = created_books["9780307743657"]

        if book1.copies.count() < 2:
            BookCopy.objects.create(book=book1, condition="new")
            BookCopy.objects.create(book=book1, condition="good")
        if book3.copies.count() < 2:
            BookCopy.objects.create(book=book3, condition="good")
            BookCopy.objects.create(book=book3, condition="worn", status="damaged")

        student = Student.objects.filter(admission_number="ADM-003").first()
        member = None
        if student:
            member, _ = Member.objects.get_or_create(
                student=student, defaults={"status": "active"}
            )
        else:
            self.stderr.write("WARNING: student ADM-003 not found; member not seeded.")

        available_copy = book1.copies.filter(status="available").first()
        if member and available_copy and not Issue.objects.filter(
            copy=available_copy, returned_on__isnull=True
        ).exists():
            due = date.today() + timedelta(
                days=LibrarySettings.get_solo().loan_duration_days
            )
            issue = Issue.objects.create(copy=available_copy, member=member, due_date=due)
            available_copy.status = "issued"
            available_copy.save(update_fields=["status"])
            self.stdout.write(self.style.SUCCESS(f"Seeded issue {issue.pk} - {available_copy.barcode} -> {member.name}."))

        self.stdout.write(
            self.style.SUCCESS(
                "Library seed complete: "
                f"{Author.objects.count()} authors, {Category.objects.count()} categories, "
                f"{Publisher.objects.count()} publishers, {Book.objects.count()} books, "
                f"{BookCopy.objects.count()} copies, {Member.objects.count()} members, "
                f"{Issue.objects.count()} issues."
            )
        )