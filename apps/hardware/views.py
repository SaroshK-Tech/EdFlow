from django.contrib import messages
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin

from .forms import DeviceForm, MaintenanceRequestForm
from .models import Device, DeviceEvent, MaintenanceRequest, TicketStatus
from .services import find_by_token, heartbeat


class DeviceListView(EdFlowMixin, SearchMixin, ListView):
    model = Device
    template_name = "hardware/device_list.html"
    context_object_name = "devices"
    paginate_by = 25
    page_title = "Devices"
    page_subtitle = "SMS gateways and connected hardware"
    active_page = "hardware"
    search_fields = ["name", "model", "serial_number", "ip_address", "location"]
    search_placeholder = "Search devices…"


class DeviceCreateView(EdFlowMixin, CreateView):
    model = Device
    form_class = DeviceForm
    template_name = "hardware/device_form.html"
    page_title = "New Device"
    page_subtitle = "Register a gateway or connected hardware"
    active_page = "hardware"

    def get_success_url(self):
        return reverse("hardware:device_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        heartbeat(self.object, "registered", "Device registered from the portal.")
        audit(self.request, "hardware", self.object.pk, "Registered device.")
        messages.success(
            self.request,
            "Device registered. Gateway token issued — configure it in the Android app.",
        )
        return response


class DeviceUpdateView(EdFlowMixin, UpdateView):
    model = Device
    form_class = DeviceForm
    template_name = "hardware/device_form.html"
    page_title = "Edit Device"
    page_subtitle = "Update device information"
    active_page = "hardware"

    def get_success_url(self):
        return reverse("hardware:device_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        audit(self.request, "hardware", self.object.pk, "Updated device.")
        messages.success(self.request, "Device saved.")
        return response


class DeviceDeleteView(EdFlowMixin, DeleteView):
    model = Device
    template_name = "hardware/confirm_delete.html"
    page_title = "Delete Device"
    active_page = "hardware"

    def get_success_url(self):
        return reverse("hardware:devices")

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        super().post(request, *args, **kwargs)
        audit(request, "hardware", obj.pk, "Deleted device.")
        messages.success(request, "Device deleted.")
        from django.shortcuts import redirect

        return redirect("hardware:devices")


class DeviceDetailView(EdFlowMixin, DetailView):
    model = Device
    template_name = "hardware/device_detail.html"
    context_object_name = "device"
    page_title = "Device"
    active_page = "hardware"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["events"] = self.object.events.all()[:50]
        from apps.communication.models import Outbox

        ctx["gateway_pending"] = (
            Outbox.objects.filter(status="pending").count()
            if self.object.device_type == "gateway"
            else 0
        )
        ctx["tickets"] = self.object.maintenance_requests.all()[:10]
        return ctx


# --- Gateway heartbeat API (hardware-level, token in URL) -------------------


@csrf_exempt
@require_POST
def device_heartbeat(request, token):
    device = find_by_token(token)
    if device is None:
        return JsonResponse({"error": "unauthorized"}, status=401)
    event_type = request.POST.get("event_type", "heartbeat")
    detail = request.POST.get("detail", "")
    sim = request.POST.get("sim_info", "")
    network = request.POST.get("network_status", "")
    battery = request.POST.get("battery_level", "")
    if sim:
        device.sim_info = sim[:120]
    if network:
        device.network_status = network[:120]
    if battery:
        try:
            device.battery_level = min(max(int(battery), 0), 100)
        except (TypeError, ValueError):
            pass
    device.last_seen = timezone.now()
    device.save(update_fields=["last_seen", "sim_info", "network_status", "battery_level", "updated_at"])
    DeviceEvent.objects.create(device=device, event_type=event_type, detail=detail[:2000])
    return JsonResponse(
        {
            "ok": True,
            "device": device.name,
            "status": device.status,
            "last_seen": device.last_seen.isoformat(),
        }
    )


# --- Maintenance / support tickets -------------------------------------------


class MaintenanceListView(EdFlowMixin, SearchMixin, ListView):
    model = MaintenanceRequest
    template_name = "hardware/maintenance_list.html"
    context_object_name = "tickets"
    paginate_by = 25
    page_title = "Maintenance Tickets"
    page_subtitle = "Device faults and repairs"
    active_page = "hardware"
    search_fields = ["ticket_number", "issue_title", "device__name", "assigned_to"]

    def get_queryset(self):
        return super().get_queryset().select_related("device")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["open_count"] = MaintenanceRequest.objects.exclude(
            status__in=[TicketStatus.RESOLVED, TicketStatus.CLOSED]
        ).count()
        ctx["by_status"] = list(
            MaintenanceRequest.objects.values("status").annotate(count=Count("id"))
        )
        return ctx


class MaintenanceCreateView(EdFlowMixin, CreateView):
    model = MaintenanceRequest
    form_class = MaintenanceRequestForm
    template_name = "hardware/maintenance_form.html"
    page_title = "New Maintenance Ticket"
    page_subtitle = "Report a device fault"
    active_page = "hardware"

    def get_initial(self):
        return {"device": self.request.GET.get("device")}

    def form_valid(self, form):
        form.instance.reported_by = self.request.user
        resp = super().form_valid(form)
        heartbeat(
            self.object.device,
            "error",
            f"Maintenance ticket {self.object.ticket_number}: {self.object.issue_title}",
        )
        audit(
            self.request,
            f"hardware.ticket {self.object.ticket_number}",
            object_type="MaintenanceRequest",
            object_id=self.object.pk,
        )
        messages.success(self.request, f"Ticket {self.object.ticket_number} opened.")
        return resp

    def get_success_url(self):
        return reverse("hardware:maintenance")


class MaintenanceUpdateView(EdFlowMixin, UpdateView):
    model = MaintenanceRequest
    form_class = MaintenanceRequestForm
    template_name = "hardware/maintenance_form.html"
    page_title = "Update Maintenance Ticket"
    active_page = "hardware"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_subtitle"] = self.object.ticket_number
        return ctx

    def form_valid(self, form):
        resp = super().form_valid(form)
        status = form.instance.status
        if status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
            MaintenanceRequest.objects.filter(pk=form.instance.pk).update(
                resolved_at=timezone.now()
            )
            heartbeat(form.instance.device, "result", f"Ticket {form.instance.ticket_number} {status}")
        messages.success(
            self.request, f"Ticket {form.instance.ticket_number} updated ({form.instance.get_status_display()})."
        )
        return resp

    def get_success_url(self):
        return reverse("hardware:maintenance")


class MaintenanceDeleteView(EdFlowMixin, DeleteView):
    model = MaintenanceRequest
    template_name = "hardware/confirm_delete.html"
    page_title = "Delete Maintenance Ticket"
    active_page = "hardware"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object_label"] = "maintenance ticket"
        ctx["cancel_url"] = reverse("hardware:maintenance")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Maintenance ticket deleted.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("hardware:maintenance")