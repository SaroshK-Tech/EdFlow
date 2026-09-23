import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin

from .forms import (
    AuthorForm,
    BookCopyForm,
    BookForm,
    CategoryForm,
    IssueForm,
    MemberForm,
    PublisherForm,
)
from .models import (
    Author,
    Book,
    BookCopy,
    Category,
    CopyStatus,
    Fine,
    Issue,
    LibrarySettings,
    Member,
    Publisher,
)


class BookListView(EdFlowMixin, SearchMixin, ListView):
    model = Book
    template_name = "library/book_list.html"
    context_object_name = "books"
    paginate_by = 20
    page_title = "Library"
    page_subtitle = "Books, copies, circulation and fines"
    active_page = "library"
    search_fields = ["title", "isbn", "author__name"]
    search_placeholder = "Search by title, ISBN or author…"

    def get_queryset(self):
        qs = super().get_queryset().select_related("author", "category", "publisher")
        category = self.request.GET.get("category", "").strip()
        if category.isdigit():
            qs = qs.filter(category_id=int(category))
        status = self.request.GET.get("status", "").strip()
        if status in dict(CopyStatus.choices):
            qs = qs.filter(copies__status=status).distinct()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["category_choices"] = Category.objects.all()
        ctx["status_choices"] = CopyStatus.choices
        ctx["current_category"] = self.request.GET.get("category", "")
        ctx["current_status"] = self.request.GET.get("status", "")
        filter_params = {}
        if ctx["current_category"]:
            filter_params["category"] = ctx["current_category"]
        if ctx["current_status"]:
            filter_params["status"] = ctx["current_status"]
        ctx["filter_params"] = filter_params
        ctx["total_books"] = Book.objects.count()
        ctx["total_copies"] = BookCopy.objects.count()
        ctx["available_copies"] = BookCopy.objects.filter(status=CopyStatus.AVAILABLE).count()
        return ctx


class AuthorCreateView(EdFlowMixin, CreateView):
    model = Author
    form_class = AuthorForm
    template_name = "library/simple_form.html"
    page_title = "Add Author"
    active_page = "library"
    extra_context = {"cancel_url": "library:list"}

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"author.create {self.object.name}")
        messages.success(self.request, f"Author {self.object.name} added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("library:list")


class CategoryCreateView(EdFlowMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "library/simple_form.html"
    page_title = "Add Category"
    active_page = "library"
    extra_context = {"cancel_url": "library:list"}

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"category.create {self.object.name}")
        messages.success(self.request, f"Category {self.object.name} added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("library:list")


class PublisherCreateView(EdFlowMixin, CreateView):
    model = Publisher
    form_class = PublisherForm
    template_name = "library/simple_form.html"
    page_title = "Add Publisher"
    active_page = "library"
    extra_context = {"cancel_url": "library:list"}

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"publisher.create {self.object.name}")
        messages.success(self.request, f"Publisher {self.object.name} added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("library:list")


class BookCreateView(EdFlowMixin, CreateView):
    model = Book
    form_class = BookForm
    template_name = "library/simple_form.html"
    page_title = "Add Book"
    page_subtitle = "Register a new title in the library catalogue"
    active_page = "library"
    extra_context = {"cancel_url": "library:list"}

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"book.create {self.object.title}")
        messages.success(self.request, f"Book “{self.object.title}” added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("library:book_detail", args=[self.object.pk])


class BookUpdateView(EdFlowMixin, UpdateView):
    model = Book
    form_class = BookForm
    template_name = "library/simple_form.html"
    context_object_name = "book"
    page_title = "Edit Book"
    active_page = "library"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = "library:book_detail"
        ctx["cancel_arg"] = self.object.pk
        ctx["page_subtitle"] = self.object.title
        return ctx

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, f"Book “{self.object.title}” updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("library:book_detail", args=[self.object.pk])


class BookDetailView(EdFlowMixin, DetailView):
    model = Book
    template_name = "library/book_detail.html"
    context_object_name = "book"
    active_page = "library"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = self.object.title
        ctx["page_subtitle"] = str(self.object.author)
        copies = self.object.copies.select_related("book")
        open_issues = Issue.objects.filter(
            copy__book=self.object, returned_on__isnull=True
        ).select_related("member", "copy")
        ctx["copies"] = copies
        ctx["open_issues"] = open_issues
        ctx["open_by_copy"] = {i.copy_id: i for i in open_issues}
        return ctx


class BookDeleteView(EdFlowMixin, DeleteView):
    model = Book
    template_name = "library/book_confirm_delete.html"
    context_object_name = "book"
    success_url = reverse_lazy("library:list")
    active_page = "library"
    extra_context = {"heading": "Delete Book", "cancel_url": "library:list"}

    def form_valid(self, form):
        if self.object.copies.exists():
            messages.error(
                self.request,
                "Cannot delete a book that still has copies — remove its copies first.",
            )
            return redirect("library:book_detail", pk=self.object.pk)
        audit(self.request, f"book.delete {self.object.pk} {self.object.title}")
        messages.success(self.request, f"Book “{self.object.title}” deleted.")
        return super().form_valid(form)


class CopyListView(EdFlowMixin, ListView):
    model = BookCopy
    template_name = "library/copy_list.html"
    context_object_name = "copies"
    paginate_by = 25
    page_title = "Book Copies"
    page_subtitle = "Physical copies, barcodes and condition"
    active_page = "library"

    def get_queryset(self):
        qs = super().get_queryset().select_related("book", "book__author")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                models.Q(barcode__icontains=q) | models.Q(book__title__icontains=q)
            )
        status = self.request.GET.get("status", "").strip()
        if status in dict(CopyStatus.choices):
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["status_choices"] = CopyStatus.choices
        ctx["current_status"] = self.request.GET.get("status", "")
        filter_params = {}
        if ctx["current_status"]:
            filter_params["status"] = ctx["current_status"]
        ctx["filter_params"] = filter_params
        ctx["search_placeholder"] = "Search by barcode or title…"
        return ctx


class CopyCreateView(EdFlowMixin, CreateView):
    model = BookCopy
    form_class = BookCopyForm
    template_name = "library/simple_form.html"
    page_title = "Add Book Copy"
    page_subtitle = "Register a physical copy with a barcode"
    active_page = "library"

    def get_initial(self):
        initial = super().get_initial()
        book = self.request.GET.get("book", "").strip()
        if book.isdigit():
            initial["book"] = int(book)
            if Book.objects.filter(pk=int(book)).exists():
                self.preselect_book = int(book)
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        book = getattr(self, "preselect_book", None)
        ctx["cancel_url"] = "library:book_detail" if book else "library:copies"
        ctx["cancel_arg"] = book
        ctx["page_subtitle"] = (
            Book.objects.filter(pk=book).values_list("title", flat=True).first()
            if book
            else "Register a physical copy with a barcode"
        )
        return ctx

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(
            self.request,
            f"copy.create {self.object.barcode} book={self.object.book_id}",
        )
        messages.success(
            self.request, f"Copy {self.object.barcode} added for “{self.object.book.title}”."
        )
        return resp

    def get_success_url(self):
        return reverse_lazy("library:book_detail", args=[self.object.book_id])


class CopyDeleteView(EdFlowMixin, DeleteView):
    model = BookCopy
    template_name = "library/copy_confirm_delete.html"
    context_object_name = "copy"
    active_page = "library"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["heading"] = "Delete Book Copy"
        ctx["cancel_url"] = "library:book_detail"
        ctx["cancel_arg"] = self.object.book_id
        return ctx

    def form_valid(self, form):
        if self.object.issues.exists():
            messages.error(
                self.request,
                "Cannot delete a copy that has issue history — withdraw or mark it lost instead.",
            )
            return redirect("library:book_detail", pk=self.object.book_id)
        audit(self.request, f"copy.delete {self.object.pk} {self.object.barcode}")
        messages.success(self.request, f"Copy {self.object.barcode} deleted.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("library:book_detail", args=[self.object.book_id])


class MemberListView(EdFlowMixin, SearchMixin, ListView):
    model = Member
    template_name = "library/member_list.html"
    context_object_name = "members"
    paginate_by = 25
    page_title = "Library Members"
    page_subtitle = "Students and staff who borrow books"
    active_page = "library"
    search_fields = [
        "name",
        "student__admission_number",
        "student__first_name",
        "student__last_name",
        "staff__employee_code",
        "staff__first_name",
        "staff__last_name",
        "phone",
    ]
    search_placeholder = "Search by name, student/staff code or phone…"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("student", "staff")
            .annotate(open_issues=Count("issues", filter=models.Q(issues__returned_on__isnull=True)))
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_count"] = Member.objects.filter(status="active").count()
        return ctx


class MemberCreateView(EdFlowMixin, CreateView):
    model = Member
    form_class = MemberForm
    template_name = "library/member_form.html"
    page_title = "Add Library Member"
    page_subtitle = "Link to a student or staff record"
    active_page = "library"
    extra_context = {"cancel_url": "library:members"}

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"member.create {self.object.pk} {self.object.name}")
        messages.success(self.request, f"Member {self.object.name} added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("library:members")


class MemberUpdateView(EdFlowMixin, UpdateView):
    model = Member
    form_class = MemberForm
    template_name = "library/member_form.html"
    context_object_name = "member"
    page_title = "Edit Library Member"
    active_page = "library"
    extra_context = {"cancel_url": "library:members"}

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, f"Member {self.object.name} updated.")
        return resp

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_subtitle"] = self.object.name
        return ctx

    def get_success_url(self):
        return reverse_lazy("library:members")


@login_required
def issue_copy(request):
    if request.method == "POST":
        form = IssueForm(request.POST)
        if form.is_valid():
            copy = form.cleaned_data["copy"]
            member = form.cleaned_data["member"]
            with transaction.atomic():
                copy = BookCopy.objects.select_for_update().get(pk=copy.pk)
                if copy.status != CopyStatus.AVAILABLE:
                    messages.error(
                        request,
                        f"Copy {copy.barcode} is {copy.get_status_display()} and cannot be issued.",
                    )
                    return redirect("library:issue")
                issue = Issue.objects.create(
                    copy=copy,
                    member=member,
                    due_date=form.cleaned_data["due_date"],
                    remark=form.cleaned_data["remark"],
                    issued_by=request.user,
                )
                copy.status = CopyStatus.ISSUED
                copy.save(update_fields=["status"])
            audit(
                request,
                f"issue.create issue={issue.pk} copy={copy.barcode} member={member.pk}",
            )
            messages.success(request, f"Issued {copy.barcode} to {member.name}.")
            return redirect("library:returns")
    else:
        initial = {}
        barcode = request.GET.get("barcode", "").strip()
        if barcode:
            initial["barcode"] = barcode.upper()
        member = request.GET.get("member", "").strip()
        if member.isdigit():
            initial["member"] = int(member)
        form = IssueForm(initial=initial)
    return render(
        request,
        "library/issue.html",
        {
            "form": form,
            "available_copies": BookCopy.objects.filter(status=CopyStatus.AVAILABLE)
            .select_related("book")
            .order_by("barcode")[:12],
            "page_title": "Issue a Book",
            "page_subtitle": "Lend an available copy to a library member",
            "active_page": "library",
        },
    )


@login_required
def returns_list(request):
    qs = (
        Issue.objects.select_related("copy__book", "member")
        .filter(returned_on__isnull=True)
        .order_by("due_date")
    )
    barcode = request.GET.get("barcode", "").strip().upper()
    member_q = request.GET.get("member", "").strip()
    if barcode:
        qs = qs.filter(copy__barcode__icontains=barcode)
    if member_q:
        qs = qs.filter(member__name__icontains=member_q)
    return render(
        request,
        "library/returns.html",
        {
            "issues": qs,
            "barcode": request.GET.get("barcode", ""),
            "member_q": member_q,
            "overdue_count": qs.filter(due_date__lt=datetime.date.today()).count(),
            "settings": LibrarySettings.get_solo(),
            "page_title": "Returns & Renewals",
            "page_subtitle": "Open issues — return books and manage due dates",
            "active_page": "library",
        },
    )


@login_required
def return_issue(request, pk):
    if request.method != "POST":
        return redirect("library:returns")
    issue = get_object_or_404(
        Issue.objects.select_related("copy", "member"), pk=pk, returned_on__isnull=True
    )
    with transaction.atomic():
        amount = issue.computed_fine
        days = issue.days_overdue
        issue.returned_on = datetime.date.today()
        if amount > 0:
            issue.fine_amount = amount
            Fine.objects.create(
                issue=issue,
                amount=amount,
                reason=f"Overdue return — {days} day(s) past the due date",
            )
        issue.save()
        issue.copy.status = CopyStatus.AVAILABLE
        issue.copy.save(update_fields=["status"])
    audit(request, f"issue.return issue={issue.pk} copy={issue.copy.barcode} fine={amount}")
    if amount > 0:
        messages.success(
            request,
            f"{issue.copy.barcode} returned. Overdue fine ₹{amount} recorded.",
        )
    else:
        messages.success(request, f"{issue.copy.barcode} returned and is available again.")
    return redirect("library:returns")


@login_required
def renew_issue(request, pk):
    if request.method != "POST":
        return redirect("library:returns")
    issue = get_object_or_404(Issue, pk=pk, returned_on__isnull=True)
    duration = LibrarySettings.get_solo().loan_duration_days
    issue.due_date = issue.due_date + datetime.timedelta(days=duration)
    issue.save(update_fields=["due_date"])
    audit(request, f"issue.renew issue={issue.pk} due={issue.due_date}")
    messages.success(request, f"Renewed {issue.copy.barcode} — new due date {issue.due_date}.")
    return redirect("library:returns")


def _mark_copy_status(request, copy, target_status, default_reason):
    if request.method != "POST":
        return redirect("library:book_detail", pk=copy.book_id)
    settings_obj = LibrarySettings.get_solo()
    raw = request.POST.get("amount", "").strip()
    try:
        amount = Decimal(raw) if raw else settings_obj.lost_book_fine
    except Exception:
        amount = settings_obj.lost_book_fine
    reason = request.POST.get("reason", "").strip() or default_reason
    with transaction.atomic():
        copy.status = target_status
        copy.save(update_fields=["status"])
        open_issue = copy.issues.filter(returned_on__isnull=True).first()
        if open_issue:
            open_issue.returned_on = datetime.date.today()
            if open_issue.remark:
                open_issue.remark += "\n" + reason
            else:
                open_issue.remark = reason
            open_issue.save(update_fields=["returned_on", "remark"])
            Fine.objects.create(issue=open_issue, amount=amount, reason=reason)
        else:
            Fine.objects.create(issue=None, amount=amount, reason=reason)
    audit(request, f"copy.{target_status} copy={copy.pk} barcode={copy.barcode} fine={amount}")
    messages.warning(
        request, f"Copy {copy.barcode} marked {copy.get_status_display()} — fine ₹{amount} recorded."
    )
    return redirect("library:book_detail", pk=copy.book_id)


@login_required
def lost_copy(request, copy_pk):
    copy = get_object_or_404(BookCopy.objects.select_related("book"), pk=copy_pk)
    return _mark_copy_status(request, copy, CopyStatus.LOST, "Copy marked lost")


@login_required
def damaged_copy(request, copy_pk):
    copy = get_object_or_404(BookCopy.objects.select_related("book"), pk=copy_pk)
    return _mark_copy_status(request, copy, CopyStatus.DAMAGED, "Copy marked damaged")


class FineListView(EdFlowMixin, ListView):
    model = Fine
    template_name = "library/fines.html"
    context_object_name = "fines"
    paginate_by = 25
    page_title = "Library Fines"
    page_subtitle = "Unpaid fines listed first"
    active_page = "library"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("issue", "issue__member", "issue__copy")
            .order_by("paid", "-created_at")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["outstanding"] = (
            Fine.objects.filter(paid=False).aggregate(total=Sum("amount"))["total"] or 0
        )
        ctx["collected"] = (
            Fine.objects.filter(paid=True).aggregate(total=Sum("amount"))["total"] or 0
        )
        return ctx


@login_required
def fine_pay(request, pk):
    fine = get_object_or_404(Fine.objects.select_related("issue"), pk=pk)
    if request.method != "POST":
        return redirect("library:fines")
    if not fine.paid:
        fine.paid = True
        fine.save(update_fields=["paid"])
        issue = fine.issue
        if issue and not issue.fine_paid:
            issue.fine_paid = True
            issue.fine_amount = Decimal("0")
            issue.save(update_fields=["fine_paid", "fine_amount"])
    audit(request, f"fine.pay fine={fine.pk} amount={fine.amount}")
    messages.success(request, f"Fine of ₹{fine.amount} marked as paid.")
    return redirect("library:fines")


class ReportsView(EdFlowMixin, TemplateView):
    template_name = "library/reports.html"
    page_title = "Library Reports"
    page_subtitle = "Collection summary, circulation and top borrowers"
    active_page = "library"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["total_books"] = Book.objects.count()
        ctx["total_copies"] = BookCopy.objects.count()
        ctx["available_copies"] = BookCopy.objects.filter(status=CopyStatus.AVAILABLE).count()
        ctx["issued_copies"] = BookCopy.objects.filter(status=CopyStatus.ISSUED).count()
        today = datetime.date.today()
        ctx["overdue_count"] = Issue.objects.filter(
            returned_on__isnull=True, due_date__lt=today
        ).count()
        ctx["fines_collected"] = (
            Fine.objects.filter(paid=True).aggregate(total=Sum("amount"))["total"] or 0
        )
        ctx["fines_outstanding"] = (
            Fine.objects.filter(paid=False).aggregate(total=Sum("amount"))["total"] or 0
        )
        ctx["top_borrowers"] = (
            Member.objects.annotate(total=Count("issues"))
            .filter(total__gt=0)
            .select_related("student", "staff")
            .order_by("-total")[:5]
        )
        ctx["overdue_issues"] = (
            Issue.objects.filter(returned_on__isnull=True, due_date__lt=today)
            .select_related("copy__book", "member")
            .order_by("due_date")
        )
        return ctx