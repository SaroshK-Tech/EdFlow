from django.conf import settings
from django.db import models
from django.utils import timezone


class Parent(models.Model):
    """Parent/guardian profile. One parent may have many children (spec §6)."""

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    relationship = models.CharField(max_length=50, blank=True)
    occupation = models.CharField(max_length=100, blank=True)

    phone = models.CharField(max_length=20, blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    emergency_contact = models.CharField(
        max_length=20,
        blank=True,
        help_text="Emergency number for this guardian (spec §6).",
    )

    students = models.ManyToManyField(
        "students.Student", related_name="guardians", blank=True
    )
    is_primary = models.BooleanField(default=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="parent_profile",
        help_text="Optional Django account so this guardian can log into the parent portal (spec §4).",
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]

    @property
    def full_name(self):
        return " ".join(p for p in (self.first_name, self.last_name) if p)

    def __str__(self):
        return self.full_name