import os

from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View

from apps.core.mixins import EdFlowMixin, SearchMixin

from .forms import BackupProfileForm
from .models import BackupJob, BackupProfile, BackupStatus
from .services import restore_backup, run_backup, verify_job

STATUSES = dict(BackupStatus.choices)


class BackupAdminMixin:
    """Backup/restore is a superuser-only capability."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return HttpResponseForbidden("Superuser access required.")
        return super().dispatch(request, *args, **kwargs)


class BackupListView(EdFlowMixin, BackupAdminMixin, ListView):
    template_name = "backup/backup_list.html"
    context_object_name = "profiles"
    page_title = "Backup & Restore"
    page_subtitle = "Offline backups to local disk, USB, HDD or network drives"
    active_page = "backup"

    def get_queryset(self):
        return BackupProfile.objects.all().annotate(job_count=Count("jobs"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["recent_jobs"] = list(
            BackupJob.objects.select_related("profile")[:8]
        )
        ctx["total_backups"] = BackupJob.objects.count()
        ctx["verified_backups"] = BackupJob.objects.filter(verified=True).count()
        last = BackupJob.objects.filter(
            status=BackupStatus.SUCCESS
        ).first()
        ctx["last_backup"] = last
        return ctx


class BackupProfileCreateView(EdFlowMixin, BackupAdminMixin, CreateView):
    template_name = "backup/profile_form.html"
    form_class = BackupProfileForm
    page_title = "Add Backup Destination"
    page_subtitle = "Local disk, USB drive or network share"
    active_page = "backup"

    def get_success_url(self):
        return reverse_lazy("backup:list")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Backup destination added.")
        return resp


class BackupProfileUpdateView(EdFlowMixin, BackupAdminMixin, UpdateView):
    template_name = "backup/profile_form.html"
    form_class = BackupProfileForm
    page_title = "Edit Backup Destination"
    page_subtitle = "Update the destination folder or retention policy"
    active_page = "backup"

    def get_queryset(self):
        return BackupProfile.objects.all()

    def get_success_url(self):
        return reverse_lazy("backup:list")

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Backup destination updated.")
        return resp


class BackupProfileDeleteView(EdFlowMixin, BackupAdminMixin, DeleteView):
    template_name = "backup/confirm_delete.html"
    page_title = "Remove Backup Destination"
    page_subtitle = "Delete the destination profile (archives on disk stay intact)"
    active_page = "backup"

    def get_queryset(self):
        return BackupProfile.objects.all()

    def get_success_url(self):
        return reverse_lazy("backup:list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Backup destination removed.")
        return super().delete(request, *args, **kwargs)


class RunBackupView(EdFlowMixin, BackupAdminMixin, View):
    def post(self, request, pk):
        profile = BackupProfile.objects.filter(pk=pk).first()
        if not profile:
            messages.error(request, "Backup destination not found.")
            return redirect("backup:list")
        job = run_backup(profile, created_by=request.user)
        if job.status == BackupStatus.SUCCESS:
            messages.success(
                request,
                f"Backup completed: {job.archive_name} ({job.human_size}). "
                f"SHA-256 {job.checksum[:12]}…",
            )
        else:
            messages.error(request, f"Backup failed: {job.error or 'unknown error'}")
        return redirect("backup:list")


class BackupHistoryView(EdFlowMixin, BackupAdminMixin, SearchMixin, ListView):
    template_name = "backup/history.html"
    context_object_name = "jobs"
    paginate_by = 20
    search_fields = ["archive_name", "profile__name", "note", "error"]
    page_title = "Backup History"
    page_subtitle = "All backup jobs with verification status"
    active_page = "backup"

    def get_queryset(self):
        qs = BackupJob.objects.select_related("profile")
        profile_id = self.request.GET.get("profile", "")
        if profile_id:
            qs = qs.filter(profile_id=profile_id)
        status = self.request.GET.get("status", "")
        if status in STATUSES:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["profiles"] = BackupProfile.objects.all()
        ctx["selected_profile"] = self.request.GET.get("profile", "")
        ctx["selected_status"] = self.request.GET.get("status", "")
        ctx["statuses"] = BackupStatus.choices
        return ctx


class BackupVerifyView(EdFlowMixin, BackupAdminMixin, View):
    def post(self, request, pk):
        job = BackupJob.objects.filter(pk=pk).first()
        if not job:
            messages.error(request, "Backup job not found.")
            return redirect("backup:history")
        verify_job(job)
        if job.verified:
            messages.success(request, f"Backup verified: {job.archive_name}")
        else:
            messages.error(
                request, f"Verification failed: {job.error or 'unknown error'}"
            )
        return redirect("backup:history")


class BackupJobDeleteView(EdFlowMixin, BackupAdminMixin, DeleteView):
    template_name = "backup/job_delete.html"
    page_title = "Delete Backup"
    page_subtitle = "Remove the archive and its history record"
    active_page = "backup"

    def get_queryset(self):
        return BackupJob.objects.all()

    def get_success_url(self):
        return reverse_lazy("backup:history")

    def delete(self, request, *args, **kwargs):
        job = self.get_object()
        if job.archive_path:
            try:
                os.remove(job.archive_path)
            except OSError:
                pass
        messages.success(request, "Backup deleted.")
        return super().delete(request, *args, **kwargs)


class BackupRestoreView(EdFlowMixin, BackupAdminMixin, View):
    template_name = "backup/restore.html"

    def _context(self, job):
        return {
            "job": job,
            "page_title": "Restore Backup",
            "page_subtitle": f"{job.archive_name}",
            "active_page": "backup",
        }

    def get(self, request, pk):
        job = BackupJob.objects.filter(pk=pk).select_related("profile").first()
        if not job:
            messages.error(request, "Backup job not found.")
            return redirect("backup:history")
        return render(request, self.template_name, self._context(job))

    def post(self, request, pk):
        job = BackupJob.objects.filter(pk=pk).first()
        if not job:
            messages.error(request, "Backup job not found.")
            return redirect("backup:history")
        confirm = request.POST.get("confirm", "").strip()
        if confirm != job.archive_name:
            messages.error(
                request,
                "Confirmation does not match the archive name. Restore aborted.",
            )
            return render(request, self.template_name, self._context(job))
        try:
            restore_backup(job, created_by=request.user)
            messages.success(request, "Backup restored successfully.")
            return redirect("backup:history")
        except Exception as exc:
            messages.error(request, f"Restore failed: {exc}")
            return redirect("backup:restore", pk=job.pk)