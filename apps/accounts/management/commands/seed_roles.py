from django.core.management.base import BaseCommand

from apps.accounts.models import create_system_roles


class Command(BaseCommand):
    help = "Seed the standard school roles (idempotent)."

    def handle(self, *args, **options):
        created = create_system_roles()
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Seeded {len(created)} system roles: "
                    + ", ".join(r.name for r in created)
                )
            )
        else:
            self.stdout.write("No new roles created (already seeded).")