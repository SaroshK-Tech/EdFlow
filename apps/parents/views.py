from django.contrib import messages
from django.db.models import Sum
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin

from .forms import ParentForm
from .models import Parent


class ParentListView(EdFlowMixin, SearchMixin, ListView):
    model = Parent
    template_name = "parents/parent_list.html"
    context_object_name = "parents"
    paginate_by = 25
    page_title = "Parents & Guardians"
    page_subtitle = "One profile can hold multiple children"
    active_page = "parents"
    search_fields = ["first_name", "last_name", "phone", "email", "whatsapp_number"]
    search_placeholder = "Search by name, phone, email…"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("students")


class ParentDetailView(EdFlowMixin, DetailView):
    model = Parent
    template_name = "parents/parent_detail.html"
    context_object_name = "guardian"
    active_page = "parents"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        parent = self.object
        ctx["page_title"] = parent.full_name
        ctx["page_subtitle"] = f"Parent / guardian profile · {parent.get_relationship_display() if hasattr(parent, 'get_relationship_display') else parent.relationship or 'Guardian'}"

        # Children with class/section and outstanding fee balance.
        from apps.fees.models import FeeVoucherItem

        children = []
        for student in parent.students.select_related("klass", "section"):
            due = (
                FeeVoucherItem.objects.filter(
                    voucher__student=student, voucher__status="issued"
                ).aggregate(total=Sum("amount") - Sum("discount"))["total"]
                or 0
            )
            paid = (
                student.payments.aggregate(total=Sum("amount"))["total"] or 0
            )
            children.append(
                {
                    "student": student,
                    "due": due,
                    "paid": paid,
                    "balance": max(due - paid, 0),
                }
            )
        ctx["children"] = children

        # Communication history involving any of the parent's children.
        from apps.communication.models import Outbox

        child_ids = list(parent.students.values_list("id", flat=True))
        ctx["messages"] = (
            Outbox.objects.filter(student_id__in=child_ids)
            .order_by("-created_at")[:25]
            if child_ids
            else []
        )

        from apps.core.models import AuditLog

        ctx["audit_logs"] = (
            AuditLog.objects.filter(
                object_type="Parent", object_id=parent.pk
            ).order_by("-created_at")[:15]
        )
        return ctx


class ParentCreateView(EdFlowMixin, CreateView):
    model = Parent
    form_class = ParentForm
    template_name = "parents/parent_form.html"
    page_title = "Add Parent / Guardian"
    active_page = "parents"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(
            self.request,
            f"parent.create {self.object.full_name}",
            object_type="Parent",
            object_id=self.object.pk,
        )
        messages.success(self.request, f"Parent {self.object.full_name} added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("parents:list")


class ParentUpdateView(EdFlowMixin, UpdateView):
    model = Parent
    form_class = ParentForm
    template_name = "parents/parent_form.html"
    context_object_name = "guardian"
    page_title = "Edit Parent / Guardian"
    active_page = "parents"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(
            self.request,
            f"parent.update {self.object.full_name}",
            object_type="Parent",
            object_id=self.object.pk,
        )
        messages.success(self.request, "Parent updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("parents:list")


class ParentDeleteView(EdFlowMixin, DeleteView):
    model = Parent
    template_name = "parents/parent_confirm_delete.html"
    context_object_name = "guardian"
    success_url = reverse_lazy("parents:list")
    active_page = "parents"

    def form_valid(self, form):
        audit(
            self.request,
            f"parent.delete {self.object.full_name}",
            object_type="Parent",
            object_id=self.object.pk,
        )
        messages.success(self.request, f"Parent {self.object.full_name} deleted.")
        return super().form_valid(form)