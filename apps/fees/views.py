from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import F, Sum
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    UpdateView,
)

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin
from apps.academics.models import Section
from apps.students.models import Student

from .forms import (
    ConcessionForm,
    FeeHeadForm,
    FeePaymentForm,
    StudentConcessionForm,
    VoucherGenerationForm,
)
from .models import (
    Concession,
    FeeHead,
    FeePayment,
    FeeVoucher,
    FeeVoucherItem,
    StudentConcession,
    VoucherStatus,
)
from .models import discount_for_fee_head


class FeeHeadListView(EdFlowMixin, SearchMixin, ListView):
    model = FeeHead
    template_name = "fees/head_list.html"
    context_object_name = "heads"
    page_title = "Fees & Finance"
    page_subtitle = "Fee structures, collections and receipts"
    active_page = "fees"
    search_fields = ["name", "description"]
    search_placeholder = "Search fee heads…"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["collected"] = FeePayment.objects.aggregate(total=Sum("amount"))["total"] or 0
        ctx["payment_count"] = FeePayment.objects.count()
        return ctx


class FeeHeadCreateView(EdFlowMixin, CreateView):
    model = FeeHead
    form_class = FeeHeadForm
    template_name = "fees/head_form.html"
    page_title = "Add Fee Head"
    active_page = "fees"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"feehead.create {self.object.name}")
        messages.success(self.request, f"Fee head {self.object.name} created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("fees:heads")


class FeeHeadUpdateView(EdFlowMixin, UpdateView):
    model = FeeHead
    form_class = FeeHeadForm
    template_name = "fees/head_form.html"
    context_object_name = "head"
    page_title = "Edit Fee Head"
    active_page = "fees"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Fee head updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("fees:heads")


class PaymentListView(EdFlowMixin, SearchMixin, ListView):
    model = FeePayment
    template_name = "fees/payment_list.html"
    context_object_name = "payments"
    paginate_by = 25
    page_title = "Payments"
    page_subtitle = "Collections and receipts"
    active_page = "fees"
    search_fields = ["receipt_number", "student__admission_number", "student__first_name", "student__last_name"]
    search_placeholder = "Search by receipt or student…"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["total"] = FeePayment.objects.aggregate(total=Sum("amount"))["total"] or 0
        return ctx


class PaymentCreateView(EdFlowMixin, CreateView):
    model = FeePayment
    form_class = FeePaymentForm
    template_name = "fees/payment_form.html"
    page_title = "Record Payment"
    active_page = "fees"

    def form_valid(self, form):
        form.instance.received_by = self.request.user
        resp = super().form_valid(form)
        audit(
            self.request,
            f"payment.create {self.object.receipt_number} amount={self.object.amount}",
        )
        messages.success(
            self.request,
            f"Payment received — {self.object.receipt_number} ({self.object.amount}).",
        )
        return resp

    def get_success_url(self):
        return reverse_lazy("fees:payments")


class VoucherListView(EdFlowMixin, SearchMixin, ListView):
    model = FeeVoucher
    template_name = "fees/voucher_list.html"
    context_object_name = "vouchers"
    paginate_by = 25
    page_title = "Fee Vouchers"
    page_subtitle = "Bulk-generated demand vouchers with fee and banking details"
    active_page = "fees"
    search_fields = [
        "voucher_number",
        "student__admission_number",
        "student__first_name",
        "student__last_name",
    ]
    search_placeholder = "Search by voucher no or student…"

    def get_queryset(self):
        qs = super().get_queryset().select_related("student", "student__klass", "student__section")
        status = self.request.GET.get("status", "")
        if status in dict(VoucherStatus.choices):
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = VoucherStatus.choices
        ctx["current_status"] = self.request.GET.get("status", "")
        ctx["voucher_total"] = (
            FeeVoucherItem.objects.filter(voucher__in=self.get_queryset())
            .aggregate(total=Sum(F("amount") - F("discount")))["total"]
            or 0
        )
        return ctx


class VoucherGenerateView(EdFlowMixin, FormView):
    """Two-phase bulk generator: choose criteria → preview → confirm."""

    template_name = "fees/voucher_generate.html"
    form_class = VoucherGenerationForm
    page_title = "Generate Vouchers"
    page_subtitle = "Bulk-create fee vouchers for a class or section"
    active_page = "fees"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("mode", "form")
        ctx["sections"] = Section.objects.select_related("klass")
        ctx["selected_section"] = self.request.POST.get("section", "")
        return ctx

    def form_valid(self, form):
        data = form.cleaned_data
        klass = data["klass"]
        section = data.get("section")
        heads = list(data["fee_heads"])
        skip_existing = data.get("skip_existing")

        base = Student.objects.filter(klass=klass).select_related("section")
        if section:
            base = base.filter(section=section)
        base = base.order_by("admission_number")

        existing_students = base.filter(vouchers__isnull=False).distinct().count()
        students = base
        if skip_existing:
            students = base.exclude(vouchers__isnull=False)
        students = list(students)

        if self.request.POST.get("confirm"):
            created = 0
            with transaction.atomic():
                for student in students:
                    voucher = FeeVoucher.objects.create(
                        student=student,
                        due_date=data["due_date"],
                        notes=data.get("notes", ""),
                        created_by=self.request.user,
                    )
                    items = []
                    for head in heads:
                        discount = discount_for_fee_head(student, head, head.amount)
                        items.append(
                            FeeVoucherItem(
                                voucher=voucher,
                                fee_head=head,
                                amount=head.amount,
                                discount=discount,
                            )
                        )
                    FeeVoucherItem.objects.bulk_create(items)
                    created += 1
            audit(self.request, f"voucher.bulk_create class={klass} count={created}")
            messages.success(
                self.request, f"Generated {created} voucher(s) for {klass}."
            )
            return redirect("fees:vouchers")

        per_student = sum((head.amount for head in heads), 0)
        preview_discount = Decimal("0")
        for student in students:
            for head in heads:
                preview_discount += discount_for_fee_head(student, head, head.amount)
        ctx = self.get_context_data(
            form=form,
            mode="preview",
            klass=klass,
            section=section,
            heads=heads,
            students=students[:200],
            student_count=len(students),
            skipped=existing_students if skip_existing else 0,
            skip_existing=skip_existing,
            per_student=per_student,
            grand_total=per_student * len(students),
            discount_total=preview_discount,
            net_total=per_student * len(students) - preview_discount,
            due_date=data["due_date"],
            notes=data.get("notes", ""),
        )
        return self.render_to_response(ctx)


class VoucherDetailView(EdFlowMixin, DetailView):
    model = FeeVoucher
    template_name = "fees/voucher_detail.html"
    context_object_name = "voucher"
    active_page = "fees"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = self.object.voucher_number
        ctx["page_subtitle"] = self.object.student.full_name
        ctx["items"] = self.object.items.select_related("fee_head")
        return ctx


class VoucherPrintView(EdFlowMixin, ListView):
    """Print many vouchers at once (page-break per voucher)."""

    model = FeeVoucher
    template_name = "fees/voucher_print.html"
    context_object_name = "vouchers"
    active_page = "fees"

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            "student", "student__klass", "student__section"
        )
        ids = self.request.GET.getlist("id")
        if ids:
            qs = qs.filter(pk__in=ids)
        status = self.request.GET.get("status", "")
        if status in dict(VoucherStatus.choices):
            qs = qs.filter(status=status)
        return qs.prefetch_related("items__fee_head")


class VoucherDeleteView(EdFlowMixin, DeleteView):
    model = FeeVoucher
    template_name = "fees/voucher_confirm_delete.html"
    context_object_name = "voucher"
    success_url = reverse_lazy("fees:vouchers")
    active_page = "fees"

    def form_valid(self, form):
        audit(self.request, f"voucher.delete {self.object.voucher_number}")
        messages.success(self.request, f"Voucher {self.object.voucher_number} deleted.")
        return super().form_valid(form)


class ConcessionListView(EdFlowMixin, SearchMixin, ListView):
    model = Concession
    template_name = "fees/concession_list.html"
    context_object_name = "concessions"
    page_title = "Scholarships & Concessions"
    page_subtitle = "Discount schemes applied automatically to fee vouchers"
    active_page = "fees"
    search_fields = ["name", "concession_type", "description"]
    search_placeholder = "Search scholarships / concessions…"


class ConcessionCreateView(EdFlowMixin, CreateView):
    model = Concession
    form_class = ConcessionForm
    template_name = "fees/concession_form.html"
    page_title = "Add Scholarship / Concession"
    active_page = "fees"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"concession.create {self.object.name}")
        messages.success(self.request, f"Scheme {self.object.name} created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("fees:concessions")


class ConcessionUpdateView(EdFlowMixin, UpdateView):
    model = Concession
    form_class = ConcessionForm
    template_name = "fees/concession_form.html"
    context_object_name = "concession"
    page_title = "Edit Scholarship / Concession"
    active_page = "fees"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"concession.update {self.object.name}")
        messages.success(self.request, "Scheme updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("fees:concessions")


class ConcessionDeleteView(EdFlowMixin, DeleteView):
    model = Concession
    template_name = "fees/concession_confirm_delete.html"
    context_object_name = "concession"
    success_url = reverse_lazy("fees:concessions")
    active_page = "fees"

    def form_valid(self, form):
        audit(self.request, f"concession.delete {self.object.name}")
        messages.success(self.request, f"Scheme {self.object.name} deleted.")
        return super().form_valid(form)


class StudentConcessionListView(EdFlowMixin, SearchMixin, ListView):
    model = StudentConcession
    template_name = "fees/student_concession_list.html"
    context_object_name = "assignments"
    page_title = "Concession Assignments"
    page_subtitle = "Which students benefit from which scheme"
    active_page = "fees"
    paginate_by = 25
    search_fields = [
        "student__admission_number",
        "student__first_name",
        "student__last_name",
        "concession__name",
    ]
    search_placeholder = "Search by student or scheme…"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("student", "student__klass", "concession")
        )


class StudentConcessionCreateView(EdFlowMixin, CreateView):
    model = StudentConcession
    form_class = StudentConcessionForm
    template_name = "fees/student_concession_form.html"
    page_title = "Assign Scholarship / Concession"
    active_page = "fees"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        resp = super().form_valid(form)
        audit(
            self.request,
            f"concession.assign {self.object.student.admission_number} "
            f"{self.object.concession.name}",
        )
        messages.success(
            self.request,
            f"{self.object.concession.name} assigned to {self.object.student.full_name}.",
        )
        return resp

    def get_success_url(self):
        return reverse_lazy("fees:concession_assignments")


class StudentConcessionDeleteView(EdFlowMixin, DeleteView):
    model = StudentConcession
    template_name = "fees/student_concession_confirm_delete.html"
    context_object_name = "assignment"
    success_url = reverse_lazy("fees:concession_assignments")
    active_page = "fees"

    def form_valid(self, form):
        audit(
            self.request,
            f"concession.unassign {self.object.student.admission_number}",
        )
        messages.success(self.request, "Assignment removed.")
        return super().form_valid(form)
