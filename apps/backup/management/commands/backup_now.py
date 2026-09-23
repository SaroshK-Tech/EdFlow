import logging

from django.core.management.base import BaseCommand

from apps.backup.models import BackupJob, BackupProfile, BackupStatus, BackupKind
from apps.backup.services import run_backup, verify_job
from apps.accounts.models import User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Run a backup now. Use --profile <name> for one profile or --all for "
        "every active profile. Intended for Windows Task Scheduler or manual runs."
    )

    def add_arguments(self, parser):
        parser.add_argument("--profile", dest="profile", default="", help="Profile name.")
        parser.add_argument("--all", action="store_true", help="All active profiles.")
        parser.add_argument("--verify", action="store_true", help="Verify after backing up.")
        parser.add_argument("--list", action="store_true", help="List profiles and exit.")

    def handle(self, *args, **options):
        if options["list"]:
            for profile in BackupProfile.objects.all():
                self.stdout.write(f"{profile.pk}\t{profile.name}\t{profile.destination_path}\t{'active' if profile.is_active else 'inactive'}")
            return

        profiles = []
        name = options["profile"].strip()
        if name:
            profiles = list(BackupProfile.objects.filter(name=name))
            if not profiles:
                self.stderr.write(f"No profile named '{name}'.")
                return
        elif options["all"]:
            profiles = list(BackupProfile.objects.filter(is_active=True))
        else:
            self.stderr.write("Specify --profile <name> or --all.")
            return

        user = User.objects.filter(is_superuser=True).order_by("id").first()
        for profile in profiles:
            self.stdout.write(f"Backing up '{profile.name}' → {profile.destination_path} …")
            job = run_backup(profile, created_by=user, kind=BackupKind.SCHEDULED)
            if job.status == BackupStatus.SUCCESS:
                self.stdout.write(f"OK  {job.archive_name} ({job.human_size}) sha256={job.checksum[:16]}…")
                if options["verify"]:
                    verify_job(job)
                    self.stdout.write("    verified" if job.verified else "    VERIFICATION FAILED")
            else:
                self.stderr.write(f"FAILED {profile.name}: {job.error}")