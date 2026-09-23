"""Non-interactive superuser bootstrap for first-run setup (spec §39).

Replaces the interactive ``createsuperuser`` in deployment scripts. Reads
ADMIN_USERNAME, ADMIN_EMAIL and ADMIN_PASSWORD from the environment (or from
command flags). Passwords must meet Django's validator strength requirements.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import create_system_roles


class Command(BaseCommand):
    help = "Create the administrator (superuser) non-interactively. Idempotent."

    def add_arguments(self, parser):
        parser.add_argument("--username", dest="username", default="")
        parser.add_argument("--email", dest="email", default="")
        parser.add_argument("--password", dest="password", default="")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reset the password if the user already exists.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"] or os.getenv("ADMIN_USERNAME", "")
        email = options["email"] or os.getenv("ADMIN_EMAIL", "")
        password = options["password"] or os.getenv("ADMIN_PASSWORD", "")

        if not username:
            raise CommandError(
                "Provide --username or set ADMIN_USERNAME in the environment."
            )
        if not password:
            raise CommandError(
                "Provide --password or set ADMIN_PASSWORD in the environment."
            )

        create_system_roles()
        User = get_user_model()

        if User.objects.filter(username=username).exists():
            if not options["force"]:
                self.stdout.write(
                    self.style.WARNING(
                        f"User '{username}' already exists — skipping (use --force "
                        "to reset its password)."
                    )
                )
                return
            user = User.objects.get(username=username)
            user.set_password(password)
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            if email:
                user.email = email
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f"Updated administrator '{username}'.")
            )
            return

        user = User.objects.create_superuser(
            username=username, email=email, password=password
        )
        user.is_active = True
        user.save()
        self.stdout.write(
            self.style.SUCCESS(f"Created administrator '{username}'.")
        )
        self.stderr.write(
            "WARNING: change the default ADMIN_PASSWORD now if you used a "
            "documented-value during setup."
        )