from django.contrib import messages
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    UpdateView,
)

from apps.academics.models import Class
from apps.core.logging import audit
from apps.core.mixins import EdFlowMixin, SearchMixin
from apps.students.models import Student

from .forms import (
    AchievementForm,
    ActionForm,
    EmergencyAnnouncementForm,
    FollowUpForm,
    IncidentForm,
    WarningForm,
)
from .models import (
    Achievement,
    Action,
    FollowUp,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    Warning,
)
from .services import (
    credit_house_points,
    notify_parent_for_incident,
    send_emergency_announcement,
)


class IncidentListView(EdFlowMixin, SearchMixin, ListView):
    model = Incident
    template_name = "discipline/incident_list.html"
    context_object_name = "incidents"
    paginate_by = 25
    page_title = "Discipline & Behaviour"
    page_subtitle = "Incidents, warnings, actions and positive achievements"
    active_page = "discipline"
    search_fields = [
        "student__admission_number",
        "student__first_name",
        "student__last_name",
        "title",
    ]
    search_placeholder = "Search by student or title…"

    def get_queryset(self):
        qs = super().get_queryset().select_related("student", "student__klass", "klass")
        status = self.request.GET.get("status", "")
        if status in dict(IncidentStatus.choices):
            qs = qs.filter(status=status)
        klass = self.request.GET.get("klass", "")
        if klass:
            qs = qs.filter(klass_id=klass)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = IncidentStatus.choices
        ctx["current_status"] = self.request.GET.get("status", "")
        ctx["classes"] = Class.objects.all()
        ctx["current_klass"] = self.request.GET.get("klass", "")
        ctx["filter_params"] = {
            k: v
            for k, v in {
                "status": ctx["current_status"],
                "klass": ctx["current_klass"],
            }.items()
            if v
        }
        qs = self.get_queryset()
        distribution = qs.values("severity").annotate(count=Count("id")).order_by("severity")
        counts = {item["severity"]: item["count"] for item in distribution}
        ctx["severity_labels"] = [
            label for value, label in IncidentSeverity.choices
        ]
        ctx["severity_values"] = [counts.get(value, 0) for value, _ in IncidentSeverity.choices]
        return ctx


class IncidentCreateView(EdFlowMixin, CreateView):
    model = Incident
    form_class = IncidentForm
    template_name = "discipline/incident_form.html"
    page_title = "Report Incident"
    page_subtitle = "Log a new discipline incident"
    active_page = "discipline"

    def form_valid(self, form):
        form.instance.reported_by = self.request.user
        resp = super().form_valid(form)
        notify_parent_for_incident(self.object)
        audit(self.request, f"incident.create {self.object.pk} {self.object.student_id}")
        messages.success(
            self.request, f"Incident recorded for {self.object.student.full_name}."
        )
        return resp

    def get_success_url(self):
        return reverse_lazy("discipline:detail", kwargs={"pk": self.object.pk})


class IncidentDetailView(EdFlowMixin, DetailView):
    model = Incident
    template_name = "discipline/incident_detail.html"
    context_object_name = "incident"
    active_page = "discipline"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        student = self.object.student
        ctx["page_title"] = self.object.title
        ctx["page_subtitle"] = self.object.student.full_name
        ctx["warnings"] = Warning.objects.filter(student=student).select_related("incident")
        ctx["actions"] = Action.objects.filter(student=student)
        ctx["achievements"] = Achievement.objects.filter(student=student)
        ctx["followups"] = self.object.followups.all()
        ctx["other_incidents"] = Incident.objects.filter(student=student).exclude(
            pk=self.object.pk
        )[:5]
        return ctx


class IncidentUpdateView(EdFlowMixin, UpdateView):
    model = Incident
    form_class = IncidentForm
    template_name = "discipline/incident_form.html"
    context_object_name = "incident"
    page_title = "Edit Incident"
    active_page = "discipline"

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Incident updated.")
        return resp

    def get_success_url(self):
        return reverse_lazy("discipline:detail", kwargs={"pk": self.object.pk})


class IncidentDeleteView(EdFlowMixin, DeleteView):
    model = Incident
    template_name = "discipline/incident_confirm_delete.html"
    context_object_name = "incident"
    success_url = reverse_lazy("discipline:list")
    active_page = "discipline"

    def form_valid(self, form):
        audit(self.request, f"incident.delete {self.object.pk}")
        messages.success(self.request, "Incident deleted.")
        return super().form_valid(form)


class WarningListView(EdFlowMixin, SearchMixin, ListView):
    model = Warning
    template_name = "discipline/warning_list.html"
    context_object_name = "warnings"
    paginate_by = 25
    page_title = "Warnings"
    page_subtitle = "Behavioural warnings issued to students"
    active_page = "discipline"
    search_fields = [
        "student__admission_number",
        "student__first_name",
        "student__last_name",
        "issued_by",
    ]
    search_placeholder = "Search by student or issuer…"

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related("student", "student__klass", "incident")
        )


class WarningCreateView(EdFlowMixin, CreateView):
    model = Warning
    form_class = WarningForm
    template_name = "discipline/warning_form.html"
    page_title = "Issue Warning"
    active_page = "discipline"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"warning.create {self.object.pk} {self.object.student_id}")
        messages.success(
            self.request, f"{self.object.get_type_display()} warning issued."
        )
        return resp

    def get_success_url(self):
        return reverse_lazy("discipline:warnings")


class ActionListView(EdFlowMixin, SearchMixin, ListView):
    model = Action
    template_name = "discipline/action_list.html"
    context_object_name = "actions"
    paginate_by = 25
    page_title = "Disciplinary Actions"
    page_subtitle = "Detentions, suspensions, improvement plans and more"
    active_page = "discipline"
    search_fields = [
        "student__admission_number",
        "student__first_name",
        "student__last_name",
    ]
    search_placeholder = "Search by student…"

    def get_queryset(self):
        return super().get_queryset().select_related("student", "student__klass")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["open_count"] = Action.objects.filter(completed=False).count()
        ctx["completed_count"] = Action.objects.filter(completed=True).count()
        return ctx


class ActionCreateView(EdFlowMixin, CreateView):
    model = Action
    form_class = ActionForm
    template_name = "discipline/action_form.html"
    page_title = "Take Action"
    active_page = "discipline"

    def form_valid(self, form):
        resp = super().form_valid(form)
        audit(self.request, f"action.create {self.object.pk} {self.object.student_id}")
        messages.success(self.request, "Disciplinary action recorded.")
        return resp

    def get_success_url(self):
        return reverse_lazy("discipline:actions")


class AchievementListView(EdFlowMixin, SearchMixin, ListView):
    model = Achievement
    template_name = "discipline/achievement_list.html"
    context_object_name = "achievements"
    paginate_by = 25
    page_title = "Achievements"
    page_subtitle = "Positive recognition and house points"
    active_page = "discipline"
    search_fields = [
        "student__admission_number",
        "student__first_name",
        "student__last_name",
        "title",
    ]
    search_placeholder = "Search by student or title…"

    def get_queryset(self):
        return super().get_queryset().select_related("student", "student__klass")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["total_points"] = (
            Achievement.objects.aggregate(total=Sum("house_points"))["total"] or 0
        )
        return ctx


class AchievementCreateView(EdFlowMixin, CreateView):
    model = Achievement
    form_class = AchievementForm
    template_name = "discipline/achievement_form.html"
    page_title = "Add Achievement"
    active_page = "discipline"

    def form_valid(self, form):
        resp = super().form_valid(form)
        credit_house_points(self.object.student, self.object)
        audit(self.request, f"achievement.create {self.object.pk} {self.object.student_id}")
        messages.success(
            self.request, f"Achievement recorded for {self.object.student.full_name}."
        )
        return resp

    def get_success_url(self):
        return reverse_lazy("discipline:achievements")


class FollowUpCreateView(EdFlowMixin, CreateView):
    model = FollowUp
    form_class = FollowUpForm
    template_name = "discipline/followup_form.html"
    active_page = "discipline"

    def get_initial(self):
        initial = super().get_initial()
        initial["owner"] = self.request.user.get_full_name() or self.request.user.username
        return initial

    def form_valid(self, form):
        form.instance.incident_id = self.kwargs["incident_pk"]
        resp = super().form_valid(form)
        audit(self.request, f"followup.create {self.object.pk}")
        messages.success(self.request, "Follow-up added to incident.")
        return resp

    def get_success_url(self):
        return reverse_lazy(
            "discipline:detail", kwargs={"pk": self.kwargs["incident_pk"]}
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        incident = get_object_or_404(Incident, pk=self.kwargs["incident_pk"])
        ctx["incident"] = incident
        ctx["page_title"] = f"Add Follow-up — {incident.title}"
        ctx["page_subtitle"] = incident.student.full_name
        return ctx


class StudentDisciplineView(EdFlowMixin, DetailView):
    model = Student
    template_name = "discipline/student.html"
    context_object_name = "student"
    pk_url_kwarg = "student_pk"
    active_page = "discipline"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = f"Discipline — {self.object.full_name}"
        ctx["page_subtitle"] = f"{self.object.admission_number} · behaviour history"
        ctx["incidents"] = Incident.objects.filter(student=self.object).select_related("klass")
        ctx["warnings"] = Warning.objects.filter(student=self.object)
        ctx["actions"] = Action.objects.filter(student=self.object)
        ctx["achievements"] = Achievement.objects.filter(student=self.object)
        ctx["open_followups"] = FollowUp.objects.filter(
            incident__student=self.object, completed=False
        ).select_related("incident")
        return ctx


class EmergencyAnnouncementView(EdFlowMixin, FormView):
    template_name = "discipline/announcement_form.html"
    form_class = EmergencyAnnouncementForm
    page_title = "Emergency Announcement"
    page_subtitle = "Broadcast a general announcement to the whole school"
    active_page = "discipline"

    def form_valid(self, form):
        title = form.cleaned_data["title"]
        message = form.cleaned_data["message"]
        sent = send_emergency_announcement(title, message, user=self.request.user)
        audit(self.request, f"announcement.emergency {title!r} delivered={sent}")
        if sent:
            messages.success(self.request, "Emergency announcement sent.")
        else:
            messages.warning(self.request, "Announcement recorded — notification channel not available.")
        return redirect("discipline:list")