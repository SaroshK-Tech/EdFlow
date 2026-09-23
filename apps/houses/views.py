from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Sum
from django.views.generic import (
    CreateView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin

from .forms import HouseActivityForm, HouseForm, HousePointForm, HouseResultForm
from .models import House, HouseActivity, HousePoint, HouseResult


class HouseListView(EdFlowMixin, SearchMixin, ListView):
    model = House
    template_name = "houses/house_list.html"
    context_object_name = "houses"
    page_title = "Houses"
    page_subtitle = "House system with captains and coordinators"
    active_page = "houses"
    search_fields = ["name", "motto", "color"]
    search_placeholder = "Search houses…"

    def get_queryset(self):
        return super().get_queryset().select_related("captain", "vice_captain", "staff_coordinator")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for house in ctx["houses"]:
            house.points_total = (
                house.points.aggregate(total=Sum("points"))["total"] or 0
            ) + (
                house.results.aggregate(total=Sum("points_awarded"))["total"] or 0
            )
        return ctx


class HouseCreateView(EdFlowMixin, CreateView):
    model = House
    form_class = HouseForm
    template_name = "houses/house_form.html"
    page_title = "Add House"
    active_page = "houses"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"house.create {self.object.name}")
        messages.success(self.request, f"House {self.object.name} created.")
        return resp

    def get_success_url(self):
        return reverse_lazy("houses:list")


class HouseUpdateView(EdFlowMixin, UpdateView):
    model = House
    form_class = HouseForm
    template_name = "houses/house_form.html"
    context_object_name = "house"
    page_title = "Edit House"
    active_page = "houses"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "House updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("houses:list")


class LeaderboardView(EdFlowMixin, TemplateView):
    template_name = "houses/leaderboard.html"
    page_title = "House Leaderboard"
    page_subtitle = "Current standing of all houses"
    active_page = "houses"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        rows = []
        top = 1
        for house in House.objects.select_related("captain").order_by("name"):
            total = (house.points.aggregate(t=Sum("points"))["t"] or 0) + (
                house.results.aggregate(t=Sum("points_awarded"))["t"] or 0
            )
            rows.append({"house": house, "total": total})
            if total > top:
                top = total
        rows.sort(key=lambda r: r["total"], reverse=True)
        for idx, row in enumerate(rows):
            row["rank"] = idx + 1
        ctx["rows"] = rows
        ctx["top_points"] = top or 1
        ctx["point_count"] = HousePoint.objects.count()
        return ctx


class HousePointCreateView(EdFlowMixin, CreateView):
    model = HousePoint
    form_class = HousePointForm
    template_name = "houses/housepoint_form.html"
    page_title = "Award House Points"
    page_subtitle = "Good deeds, achievements and all-around effort"
    active_page = "houses"

    def form_valid(self, form):
        form.instance.awarded_by = self.request.user
        resp = super().form_valid(form)
        audit(
            self.request,
            f"house.points_award {self.object.house.name} "
            f"points={self.object.points} by_teacher={self.object.awarded_by_id}",
        )
        messages.success(
            self.request,
            f"Awarded {self.object.points} point(s) to {self.object.house.name}.",
        )
        return resp

    def get_success_url(self):
        return reverse_lazy("houses:leaderboard")


class HousePointListView(EdFlowMixin, SearchMixin, ListView):
    model = HousePoint
    template_name = "houses/housepoint_list.html"
    context_object_name = "points"
    paginate_by = 25
    page_title = "House Points"
    page_subtitle = "All awarded points across houses"
    active_page = "houses"
    search_fields = ["house__name", "reason", "student__first_name", "student__last_name"]
    search_placeholder = "Search points…"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("house", "student", "awarded_by")
        )


class HouseActivityListView(EdFlowMixin, ListView):
    model = HouseActivity
    template_name = "houses/activity_list.html"
    context_object_name = "activities"
    page_title = "House Activities"
    page_subtitle = "Events, competitions and practices"
    active_page = "houses"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("house")
            .prefetch_related("results__house")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["activity_count"] = HouseActivity.objects.count()
        return ctx


class HouseActivityCreateView(EdFlowMixin, CreateView):
    model = HouseActivity
    form_class = HouseActivityForm
    template_name = "houses/activity_form.html"
    page_title = "Add Activity"
    active_page = "houses"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"house.activity_create {self.object.name}")
        messages.success(self.request, f"Activity {self.object.name} added.")
        return resp

    def get_success_url(self):
        return reverse_lazy("houses:activities")


class HouseResultCreateView(EdFlowMixin, CreateView):
    model = HouseResult
    form_class = HouseResultForm
    template_name = "houses/result_form.html"
    page_title = "Record Result"
    page_subtitle = "Rank and points for a house in an activity"
    active_page = "houses"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(
            self.request,
            f"house.result {self.object.activity.name} {self.object.house.name} "
            f"rank={self.object.rank} points={self.object.points_awarded}",
        )
        messages.success(
            self.request,
            f"Recorded {self.object.house.name} result in {self.object.activity.name}.",
        )
        return resp

    def get_success_url(self):
        return reverse_lazy("houses:activities")