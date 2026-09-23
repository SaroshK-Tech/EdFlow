from django.core.management.base import BaseCommand

from apps.communication.models import Outbox, OutboxStatus
from apps.communication.services import autosend, retry_message


class Command(BaseCommand):
    help = "Process the outbound message queue for offline/dev environments."

    def add_arguments(self, parser):
        parser.add_argument(
            "--retry-failed",
            action="store_true",
            help="Re-queue failed messages (up to the retry cap) first.",
        )
        parser.add_argument(
            "--limit", type=int, default=50, help="Max messages to claim at once."
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Claim without marking messages sent (simulate a gateway).",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if options["retry_failed"]:
            requeued = 0
            for outbox in Outbox.objects.filter(status=OutboxStatus.FAILED):
                if outbox.attempt_count >= 3:
                    continue
                if retry_message(outbox):
                    requeued += 1
            self.stdout.write(self.style.SUCCESS(f"{requeued} failed message(s) re-queued."))

        if options["dry_run"]:
            from apps.communication.services import claim_due

            claimed = claim_due(limit)
            self.stdout.write(
                self.style.WARNING(f"[dry-run] claimed {len(claimed)} message(s).")
            )
            return
        claimed, sent = autosend(limit)
        self.stdout.write(
            self.style.SUCCESS(
                f"{claimed} claimed, {sent} marked as sent (offline simulator)."
            )
        )