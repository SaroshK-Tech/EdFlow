from datetime import date, timedelta

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin
from apps.students.models import Student

from .forms import DriverForm, RouteForm, StopForm, TransportAssignmentForm, VehicleForm
from .models import Driver, Route, StaffAssignment, Stop, TransportAssignment, Vehicle


class VehicleListView(EdFlowMixin, SearchMixin, ListView):
    model = Vehicle
    template_name = "transport/vehicle_list.html"
    context_object_name = "vehicles"
    page_title = "Transport"
    page_subtitle = "Vehicles, drivers, routes and assignments"
    active_page = "transport"
    search_fields = ["registration_number", "model", "owner"]
    search_placeholder = "Search vehicles…"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["route_count"] = Route.objects.count()
        ctx["driver_count"] = Driver.objects.count()
        ctx["active_assigns"] = TransportAssignment.objects.filter(is_active=True).count()
        return ctx


class VehicleCreateView(EdFlowMixin, CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = "transport/vehicle_form.html"
    page_title = "Add Vehicle"
    active_page = "transport"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"vehicle.create {self.object.registration_number}")
        messages.success(self.request, f"Vehicle {self.object} added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("transport:list")


class VehicleUpdateView(EdFlowMixin, UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = "transport/vehicle_form.html"
    context_object_name = "vehicle"
    page_title = "Edit Vehicle"
    active_page = "transport"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Vehicle updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("transport:list")


class VehicleDeleteView(EdFlowMixin, DeleteView):
    model = Vehicle
    template_name = "transport/vehicle_confirm_delete.html"
    context_object_name = "vehicle"
    success_url = reverse_lazy("transport:list")
    active_page = "transport"

    def form_valid(self, form):
        audit(self.request, f"vehicle.delete {self.object.registration_number}")
        messages.success(self.request, f"Vehicle {self.object} deleted.")
        return super().form_valid(form)


class RouteListView(EdFlowMixin, SearchMixin, ListView):
    model = Route
    template_name = "transport/route_list.html"
    context_object_name = "routes"
    page_title = "Routes"
    page_subtitle = "Bus routes with vehicles, drivers and stops"
    active_page = "transport"
    search_fields = ["name", "description"]
    search_placeholder = "Search routes…"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("vehicle", "assigned_driver")
            .annotate(stop_count=Count("stops", distinct=True))
        )


class RouteCreateView(EdFlowMixin, CreateView):
    model = Route
    form_class = RouteForm
    template_name = "transport/route_form.html"
    page_title = "Add Route"
    active_page = "transport"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"route.create {self.object.name}")
        messages.success(self.request, f"Route {self.object.name} created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("transport:routes")


class RouteUpdateView(EdFlowMixin, UpdateView):
    model = Route
    form_class = RouteForm
    template_name = "transport/route_form.html"
    context_object_name = "route"
    page_title = "Edit Route"
    active_page = "transport"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Route updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("transport:routes")


class RouteDetailView(EdFlowMixin, DetailView):
    model = Route
    template_name = "transport/route_detail.html"
    context_object_name = "route"
    active_page = "transport"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        route = self.object
        ctx["page_title"] = route.name
        ctx["page_subtitle"] = route.description or "Route details"
        ctx["stops"] = route.stops.order_by("sequence")
        student_count = TransportAssignment.objects.filter(
            route=route, is_active=True
        ).count()
        staff_count = StaffAssignment.objects.filter(route=route, active=True).count()
        ctx["student_count"] = student_count
        ctx["staff_count"] = staff_count
        ctx["loading"] = student_count + staff_count
        ctx["capacity"] = route.vehicle.capacity if route.vehicle else None
        if route.vehicle and route.vehicle.capacity:
            ctx["loading_pct"] = round(
                (student_count + staff_count) / route.vehicle.capacity * 100
            )
        else:
            ctx["loading_pct"] = 0
        return ctx


class StopListView(EdFlowMixin, ListView):
    model = Stop
    template_name = "transport/stop_list.html"
    context_object_name = "stops"
    page_title = "Stops"
    page_subtitle = "Pickup and drop-off points across routes"
    active_page = "transport"

    def get_queryset(self):
        return (
            super().get_queryset().select_related("route").order_by("route__name", "sequence")
        )


class StopCreateView(EdFlowMixin, CreateView):
    model = Stop
    form_class = StopForm
    template_name = "transport/stop_form.html"
    page_title = "Add Stop"
    active_page = "transport"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"stop.create {self.object.name} route={self.object.route}")
        messages.success(self.request, f"Stop {self.object.name} added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("transport:stops")


class StopDeleteView(EdFlowMixin, DeleteView):
    model = Stop
    template_name = "transport/stop_confirm_delete.html"
    context_object_name = "stop"
    success_url = reverse_lazy("transport:stops")
    active_page = "transport"

    def form_valid(self, form):
        audit(self.request, f"stop.delete {self.object.name}")
        messages.success(self.request, f"Stop {self.object.name} deleted.")
        return super().form_valid(form)


class DriverListView(EdFlowMixin, SearchMixin, ListView):
    model = Driver
    template_name = "transport/driver_list.html"
    context_object_name = "drivers"
    page_title = "Drivers"
    page_subtitle = "Transport drivers and licence documents"
    active_page = "transport"
    search_fields = ["name", "phone", "license_number"]
    search_placeholder = "Search drivers…"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["today"] = date.today()
        return ctx


class DriverCreateView(EdFlowMixin, CreateView):
    model = Driver
    form_class = DriverForm
    template_name = "transport/driver_form.html"
    page_title = "Add Driver"
    active_page = "transport"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"driver.create {self.object.name}")
        messages.success(self.request, f"Driver {self.object.name} added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("transport:drivers")


class DriverUpdateView(EdFlowMixin, UpdateView):
    model = Driver
    form_class = DriverForm
    template_name = "transport/driver_form.html"
    context_object_name = "driver"
    page_title = "Edit Driver"
    active_page = "transport"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Driver updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("transport:drivers")


class TransportAssignView(EdFlowMixin, FormView):
    """Student picker + assignment form + active assignment list."""

    template_name = "transport/assign.html"
    form_class = TransportAssignmentForm
    page_title = "Transport Assignments"
    page_subtitle = "Allocate students to routes, stops and directions"
    active_page = "transport"

    def get_student(self):
        sid = self.request.GET.get("student_id")
        if not sid and self.request.method == "POST":
            sid = self.request.POST.get("student")
        if not sid:
            return None
        try:
            return Student.objects.get(pk=sid)
        except (Student.DoesNotExist, TypeError, ValueError):
            return None

    def get_matching_students(self):
        q = self.request.GET.get("q", "").strip()
        qs = Student.objects.select_related("klass", "house").order_by("admission_number")
        if q:
            qs = qs.filter(
                Q(admission_number__icontains=q)
                | Q(first_name__icontains=q)
                | Q(middle_name__icontains=q)
                | Q(last_name__icontains=q)
            )
        return qs[:40]

    def get_initial(self):
        initial = super().get_initial()
        student = self.get_student()
        if not student:
            return initial
        existing = TransportAssignment.objects.filter(student=student).last()
        if existing:
            initial["route"] = existing.route
            initial["direction"] = existing.direction
            initial["transport_fee_per_term"] = existing.transport_fee_per_term
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["picked_student"] = self.get_student()
        ctx["students"] = self.get_matching_students()
        ctx["assignments"] = (
            TransportAssignment.objects.filter(is_active=True)
            .select_related("student", "route", "stop")
            .order_by("-created_at")[:60]
        )
        return ctx

    def form_valid(self, form):
        student = self.get_student()
        if not student:
            messages.error(self.request, "Please pick a student first.")
            return redirect("transport:assign")
        form.instance.student = student
        try:
            with transaction.atomic():
                self.object = form.save()
        except IntegrityError:
            messages.error(
                self.request,
                "An assignment already exists for this student and direction.",
            )
            return self.render_to_response(self.get_context_data(form=form))
        audit(
            self.request,
            f"transport.assign {student.admission_number} {self.object.route.name} "
            f"{self.object.get_direction_display()} fee={self.object.transport_fee_per_term}",
        )
        messages.success(
            self.request,
            f"Assigned {student.full_name} to {self.object.route.name} "
            f"({self.object.get_direction_display()}).",
        )
        return redirect(f"{reverse_lazy('transport:assign')}?student_id={student.pk}")


class AssignmentDeleteView(EdFlowMixin, DeleteView):
    model = TransportAssignment
    template_name = "transport/assignment_confirm_delete.html"
    context_object_name = "assignment"
    success_url = reverse_lazy("transport:assign")
    active_page = "transport"

    def form_valid(self, form):
        audit(
            self.request,
            f"transport.assignment_delete {self.object.student.admission_number} "
            f"{self.object.route.name}",
        )
        messages.success(self.request, "Assignment removed.")
        return super().form_valid(form)


class TransportReportsView(EdFlowMixin, TemplateView):
    template_name = "transport/reports.html"
    page_title = "Transport Reports"
    page_subtitle = "Route loading and driver document expiries"
    active_page = "transport"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        rows = []
        for route in Route.objects.select_related("vehicle").order_by("name"):
            students = TransportAssignment.objects.filter(
                route=route, is_active=True
            ).count()
            staff = StaffAssignment.objects.filter(route=route, active=True).count()
            total = students + staff
            capacity = route.vehicle.capacity if route.vehicle else 0
            pct = round(total / capacity * 100) if capacity else 0
            rows.append(
                {
                    "route": route,
                    "students": students,
                    "staff": staff,
                    "total": total,
                    "capacity": capacity,
                    "pct": min(pct, 100),
                    "over": capacity > 0 and total > capacity,
                }
            )
        ctx["route_rows"] = rows

        today = date.today()
        soon = today + timedelta(days=30)
        docs = []
        for driver in Driver.objects.filter(license_expiry__isnull=False).order_by(
            "license_expiry"
        ):
            days_left = (driver.license_expiry - today).days
            if driver.license_expiry < today:
                status = "expired"
            elif driver.license_expiry <= soon:
                status = "expiring"
            else:
                status = "ok"
            docs.append({"driver": driver, "status": status, "days_left": days_left})
        ctx["driver_docs"] = docs
        return ctx