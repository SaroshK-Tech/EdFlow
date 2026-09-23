import json

from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin

from .forms import ComposeForm, MessageTemplateForm
from .models import (
    Channel,
    MessageBatch,
    MessageTemplate,
    Outbox,
    OutboxStatus,
    Priority,
)
from .services import (
    autosend,
    claim_due,
    enqueue_messages,
    report_results,
    resolve_recipients,
    retry_message,
)

_GATEWAY_TOKEN = None


def _gateway_token():
    global _GATEWAY_TOKEN
    if _GATEWAY_TOKEN is None:
        from django.conf import settings

        _GATEWAY_TOKEN = getattr(settings, "COMMUNICATION_GATEWAY_TOKEN", "")
    return _GATEWAY_TOKEN


def _authorize_gateway(request):
    token = request.headers.get("X-Gateway-Token", "")
    return bool(_gateway_token()) and token == _gateway_token()


class CommunicationDashboardView(EdFlowMixin, TemplateView):
    template_name = "communication/dashboard.html"
    page_title = "Message Center"
    page_subtitle = "SMS & WhatsApp communication queue"
    active_page = "communication"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        status = self.request.GET.get("status", "").strip()
        qs = Outbox.objects.all()
        if status in dict(OutboxStatus.choices):
            qs = qs.filter(status=status)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(recipient__icontains=q) | Q(message__icontains=q))
        ctx["status"] = status
        ctx["q"] = q
        ctx["status_options"] = OutboxStatus.choices
        ctx["messages_qs"] = qs[:80]
        ctx["total_count"] = Outbox.objects.count()
        ctx["batch_count"] = MessageBatch.objects.count()
        ctx["template_count"] = MessageTemplate.objects.count()
        counts = dict(
            Outbox.objects.values_list("status")
            .annotate(total=Count("id"))
            .values_list("status", "total")
        )
        ctx["counts"] = {s: counts.get(s, 0) for s, _ in OutboxStatus.choices}
        ctx["recent_batches"] = MessageBatch.objects.all()[:8]
        return ctx


class BatchListView(EdFlowMixin, SearchMixin, ListView):
    model = MessageBatch
    template_name = "communication/batch_list.html"
    paginate_by = 25
    page_title = "Message Batches"
    page_subtitle = "Groups of sent or scheduled messages"
    active_page = "communication"
    search_fields = ["subject"]
    search_placeholder = "Search batches…"


class BatchDetailView(EdFlowMixin, DetailView):
    model = MessageBatch
    template_name = "communication/batch_detail.html"
    context_object_name = "batch"
    page_title = "Batch Detail"
    active_page = "communication"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["messages_qs"] = self.object.messages.all()[:100]
        return ctx


class ComposeMessageView(EdFlowMixin, TemplateView):
    template_name = "communication/compose.html"
    page_title = "Compose Message"
    page_subtitle = "Send SMS or WhatsApp to parents and staff"
    active_page = "communication"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = ComposeForm(self.request.POST or None)
        return ctx

    def post(self, request, *args, **kwargs):
        form = ComposeForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        data = form.cleaned_data
        if data["schedule_date"] and data["schedule_time"]:
            scheduled_for = timezone.make_aware(
                timezone.datetime.combine(data["schedule_date"], data["schedule_time"])
            )
        else:
            scheduled_for = None

        klass = None
        if data["to_whom"] in ("class",) and data["klass"]:
            from apps.academics.models import Class

            klass = Class.objects.filter(pk=data["klass"]).first()
        recipients = resolve_recipients(
            data["to_whom"],
            klass=klass,
            manual_text=data.get("manual_numbers", ""),
        )
        if not recipients:
            messages.error(request, "No recipients with a valid phone number were found.")
            return self.render_to_response(self.get_context_data(form=form))

        template = None
        if data["template"]:
            template = MessageTemplate.objects.filter(pk=data["template"]).first()

        batch = MessageBatch.objects.create(
            subject=(template.name if template else "Custom message"),
            channel=data["channel"],
            created_by=request.user,
        )
        created = enqueue_messages(
            recipients,
            data["message"] or template.body if template else data["message"],
            template=template,
            channel=data["channel"],
            priority=data["priority"],
            scheduled_for=scheduled_for,
            batch=batch,
        )
        audit(
            request,
            "communication",
            created
            if request.user.has_perm("communication.view_outbox")
            else "queued_messages",
            f"Queued {created} message(s).",
        )
        if created:
            messages.success(request, f"Queued {created} message(s).")
        else:
            messages.warning(request, "Nothing was queued — no valid recipients.")
        return self.redirect_to_batch(request, batch)

    def redirect_to_batch(self, request, batch):
        from django.shortcuts import redirect

        if batch and batch.pk:
            return redirect("communication:batch_detail", pk=batch.pk)
        return redirect("communication:list")


class OutboxDetailView(EdFlowMixin, DetailView):
    model = Outbox
    template_name = "communication/outbox_detail.html"
    context_object_name = "outbox"
    page_title = "Message Detail"
    active_page = "communication"


class OutboxCancelView(EdFlowMixin, DetailView):
    model = Outbox
    template_name = "communication/confirm_cancel.html"
    active_page = "communication"
    page_title = "Cancel Message"

    def post(self, request, *args, **kwargs):
        outbox = self.get_object()
        if outbox.status in (OutboxStatus.PENDING, OutboxStatus.SCHEDULED):
            outbox.status = OutboxStatus.CANCELLED
            outbox.save(update_fields=["status"])
            audit(request, "communication", outbox.pk, "Cancelled queued message.")
            messages.success(request, "Message cancelled.")
        else:
            messages.warning(request, "Only pending or scheduled messages can be cancelled.")
        return redirect_result(request, outbox)


class OutboxRetryView(EdFlowMixin, View):
    model = Outbox

    def post(self, request, *args, **kwargs):
        outbox = Outbox.objects.filter(pk=kwargs.get("pk")).first()
        if outbox and retry_message(outbox):
            audit(request, "communication", outbox.pk, "Requeued failed message.")
            messages.success(request, "Message re-queued.")
        else:
            messages.warning(request, "Message could not be re-queued.")
        return redirect_result(request, outbox)


def redirect_result(request, outbox):
    from django.shortcuts import redirect

    if outbox is not None:
        return redirect("communication:message_detail", pk=outbox.pk)
    return redirect("communication:list")


class TemplateListView(EdFlowMixin, SearchMixin, ListView):
    model = MessageTemplate
    template_name = "communication/template_list.html"
    paginate_by = 25
    page_title = "Message Templates"
    page_subtitle = "Customizable templates (spec §13)"
    active_page = "communication"
    context_object_name = "templates"
    search_fields = ["name", "key"]
    search_placeholder = "Search templates…"


class TemplateCreateView(EdFlowMixin, CreateView):
    model = MessageTemplate
    form_class = MessageTemplateForm
    template_name = "communication/template_form.html"
    success_url = reverse_lazy("communication:templates")
    page_title = "New Template"
    page_subtitle = "Create a message template"
    active_page = "communication"

    def form_valid(self, form):
        form.instance.is_active = True
        response = super().form_valid(form)
        audit(self.request, "communication", self.object.pk, "Created message template.")
        messages.success(self.request, "Template created.")
        return response


class TemplateUpdateView(EdFlowMixin, UpdateView):
    model = MessageTemplate
    form_class = MessageTemplateForm
    template_name = "communication/template_form.html"
    page_title = "Edit Template"
    page_subtitle = "Customize the message body and placeholders"
    active_page = "communication"

    def get_success_url(self):
        return reverse("communication:templates")

    def form_valid(self, form):
        response = super().form_valid(form)
        audit(self.request, "communication", self.object.pk, "Updated message template.")
        messages.success(self.request, "Template saved.")
        return response


class TemplateDeleteView(EdFlowMixin, DeleteView):
    model = MessageTemplate
    template_name = "communication/confirm_delete.html"
    page_title = "Delete Template"
    active_page = "communication"

    def get_success_url(self):
        return reverse("communication:templates")

    def get_object(self, queryset=None):
        return super().get_object(queryset)

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.is_system:
            messages.error(request, "System templates cannot be deleted.")
            return redirect_result(request, None)
        audit(request, "communication", obj.pk, "Deleted message template.")
        messages.success(request, "Template deleted.")
        return super().post(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Android Communication Gateway API (offline, local LAN/USB).  Token protected.
# ---------------------------------------------------------------------------


@csrf_exempt
@require_POST
def gateway_claim(request):
    """The Android gateway pulls a batch of due messages."""
    if not _authorize_gateway(request):
        return JsonResponse({"error": "unauthorized"}, status=401)
    try:
        limit = int(request.POST.get("limit", 50))
        limit = min(max(limit, 1), 200)
    except (TypeError, ValueError):
        limit = 50
    claimed = claim_due(limit)
    payload = [
        {
            "id": m.pk,
            "to": m.recipient,
            "channel": m.channel,
            "message": m.message,
            "priority": m.priority,
        }
        for m in claimed
    ]
    return JsonResponse({"claimed": payload})


@csrf_exempt
@require_POST
def gateway_report(request):
    """The Android gateway reports per-message send results."""
    if not _authorize_gateway(request):
        return JsonResponse({"error": "unauthorized"}, status=401)
    try:
        rows = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        rows = request.POST.getlist("results[]")
    if not isinstance(rows, list):
        rows = [rows]
    updated = report_results(rows)
    return JsonResponse(updated)


@require_GET
def gateway_health(request):
    """Heartbeat the gateway uses to confirm reachability."""
    if not _authorize_gateway(request):
        return JsonResponse({"error": "unauthorized"}, status=401)
    counts = dict(Outbox.objects.values_list("status").annotate(total=Count("id")))
    return JsonResponse({"ok": True, "pending": counts.get("pending", 0),
                         "processing": counts.get("processing", 0)})