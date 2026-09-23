"""Celery tasks for backup (spec §29 background processing)."""

import logging

from celery import shared_task

from apps.backup.models import BackupProfile, BackupKind

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def backup_profile_task(self, profile_pk, verify=False):
    """Run one backup profile in the background; retries transient errors."""
    from apps.backup.models import BackupStatus
    from apps.backup.services import run_backup, verify_job
    from apps.accounts.models import User

    try:
        profile = BackupProfile.objects.get(pk=profile_pk)
    except BackupProfile.DoesNotExist:
        return {"status": "skipped", "reason": "profile missing"}

    user = User.objects.filter(is_superuser=True).order_by("id").first()
    job = run_backup(profile, created_by=user, kind=BackupKind.SCHEDULED)
    if job.status == BackupStatus.SUCCESS:
        if verify:
            verify_job(job)
        result = {"status": job.status, "job": job.pk, "verified": job.verified}
    else:
        result = {"status": job.status, "error": job.error}
        raise self.retry(exc=RuntimeError(job.error or "backup failed"))
    return result


@shared_task
def backup_all_task(verify=False):
    """Back up every active profile; used by Task Scheduler / Celery beat."""
    results = []
    for profile in BackupProfile.objects.filter(is_active=True):
        try:
            results.append(backup_profile_task.run(profile.pk, verify=verify))
        except Exception as exc:  # pragma: no cover - task already reports
            results.append({"pk": profile.pk, "error": str(exc)})
    return results